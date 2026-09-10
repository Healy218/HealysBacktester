"""User-confirmed option positions, separate from every expert's paper ledger."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
import re
import time

HELP = ('Tap ✅ Taken on an alert, or reply taken.\n'
        'Manual: /taken TRADE_ID [quantity @ fill_price]\n'
        'Different contract: /taken TRADE_ID [quantity @ fill_price] contract OCC_SYMBOL\n'
        '/selllist — tracked trades\n/sold TRADE_ID — mark a trade closed')


def trade_id(key):
    return hashlib.sha256(key.encode()).hexdigest()[:12].upper()


def install(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS trade_messages(message_id INTEGER PRIMARY KEY, candidate_key TEXT);
        CREATE TABLE IF NOT EXISTS taken_trades(id TEXT PRIMARY KEY, candidate_key TEXT UNIQUE,
            context TEXT NOT NULL, quantity INTEGER, fill_price REAL, status TEXT NOT NULL,
            taken_at REAL, closed_at REAL, last_checked TEXT, exit_notice TEXT, notice_sent INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS trade_commands(update_id INTEGER PRIMARY KEY, response TEXT NOT NULL);
    ''')
    db.execute('BEGIN IMMEDIATE')
    cols = {r[1] for r in db.execute('PRAGMA table_info(taken_trades)')}
    if 'monitor_error' not in cols:
        db.execute('ALTER TABLE taken_trades ADD COLUMN monitor_error TEXT')
    if 'monitor_error_sent' not in cols:
        db.execute('ALTER TABLE taken_trades ADD COLUMN monitor_error_sent INTEGER DEFAULT 0')


def context_for(payload, *, strategy, params, direction, spot, entry_ts, sim_start):
    from nn_meta import config
    return dict(symbol=payload, strategy=strategy, params=params, direction=int(direction),
                spot=float(spot), entry_ts=str(entry_ts), sim_start=str(sim_start),
                sim_config=dict(config.SIM_CONFIG))


def ready(context):
    return (isinstance(context, dict) and bool(context.get('contract')) and
            bool(context.get('strategy')) and isinstance(context.get('params'), dict) and
            bool(context.get('sim_config')) and context.get('direction') in (0, 1))


def _candidate(db, ident):
    matches = db.execute('SELECT * FROM candidates WHERE trade_ref=?', (ident.upper(),)).fetchall()
    if len(matches) != 1:
        raise ValueError('Trade ID not found. Reply taken to the original alert or copy its Trade ID.')
    return matches[0]


def _reply_id(db, message):
    reply = message.get('reply_to_message', {})
    row = db.execute('SELECT candidate_key FROM trade_messages WHERE message_id=?', (reply.get('message_id'),)).fetchone()
    if row:
        return trade_id(row['candidate_key'])
    # Older alerts predate message-ID capture. Match the complete saved body;
    # never infer a trade from a ticker mentioned in arbitrary text.
    body = reply.get('text', '').partition('\n')[2]
    old = db.execute("SELECT key FROM candidates WHERE status='sent' AND message=?", (body,)).fetchall()
    if len(old) == 1:
        return trade_id(old[0]['key'])
    raise ValueError('Reply to an original entry alert, or use /taken TRADE_ID.')



def recover_context(row):
    """Older queue rows lacked context; require a matching frozen parameter label."""
    from nn_meta import config
    from nn_meta.live.feeds.contracts import load_listing, resolve_occ
    message = row['message']
    trigger = re.search(r'^trigger: (\w+) \(([^\n]*?)\)', message, re.M)
    bar = re.search(r'^bar: (.+?) UTC · spot \$([\d,.]+)', message, re.M)
    if not trigger or not bar or row['expert'] not in ('v3', 'v31', 'v4', 'v5'):
        return {}
    pool = 'v31' if row['expert'] == 'v4' else row['expert']
    try:
        spec = json.loads((config.ROOT / f'artifacts_{pool}' / 'baseline_spec.json').read_text())
        strategy = trigger[1]
        frozen = spec['symbols'][row['symbol']]['strategies'][strategy]
        if frozen.get('param_label') != trigger[2]:
            return {}
        if row['side'] not in ('BUY PUT', 'BUY CALL'):
            return {}
        direction = 1 if row['side'] == 'BUY PUT' else 0
        stamp = datetime.fromisoformat(bar[1])
        spot = float(bar[2].replace(',', ''))
        match = re.search(r'^contract:.*\(([A-Z0-9.]+)\)$', message, re.M)
        occ = match[1] if match else None
        if not occ:
            cache = 'data_cache_v5' if pool == 'v5' else 'data_cache_v3' if pool == 'v31' else 'data_cache'
            listing = load_listing(config.ROOT / cache / 'contracts.parquet')
            dte_match = re.search(r'\bDTE (\d+)', message) or re.search(r'~(\d+) DTE', message)
            dte = int(dte_match[1]) if dte_match else frozen['dte']
            occ = resolve_occ(row['symbol'], 'P' if direction else 'C', spot, dte, stamp, listing=listing) if listing is not None else None
        ctx = context_for(row['symbol'], strategy=strategy, params=frozen['params'], direction=direction, spot=spot, entry_ts=str(stamp), sim_start=str(stamp.date() - timedelta(days=60)))
        ctx.update(contract=occ, expert=row['expert'], warmup_date_only=True)
        return ctx
    except (KeyError, ValueError, OSError):
        return {}


def _parse_fill(tokens):
    contract = None
    if 'contract' in [t.lower() for t in tokens]:
        i = [t.lower() for t in tokens].index('contract')
        if len(tokens) != i + 2:
            raise ValueError('Use contract OCC_SYMBOL at the end of the command.')
        contract = tokens[i+1].upper().removeprefix('O:')
        tokens = tokens[:i]
    if not tokens:
        return None, None, contract
    match = re.fullmatch(r'(\d+)\s*@\s*\$?(\d+(?:\.\d+)?)', ' '.join(tokens))
    if not match:
        raise ValueError('Use quantity @ fill_price, for example: taken 2 @ 1.35')
    quantity, price = int(match[1]), float(match[2])
    if not 1 <= quantity <= 100000 or not math.isfinite(price) or price <= 0:
        raise ValueError('Quantity and option fill price must be positive.')
    return quantity, price, contract


def _validate_contract(occ, ctx):
    from options.data.provider import parse_occ_symbol
    from nn_meta import config
    try:
        symbol, expiry, right, strike = parse_occ_symbol(occ)
    except Exception:
        raise ValueError('Invalid OCC contract symbol.') from None
    expected = config.TICKER_ALIASES.get(ctx['symbol'], ctx['symbol'])
    if symbol not in (ctx['symbol'], expected) or right.upper() != ('P' if ctx['direction'] else 'C'):
        raise ValueError('Contract must match the alert’s symbol and call/put direction.')
    if expiry < datetime.now(timezone.utc).date():
        raise ValueError('That contract has expired; use the contract you currently hold.')


def _listing(db):
    rows = db.execute("SELECT * FROM taken_trades WHERE status!='closed' ORDER BY taken_at").fetchall()
    if not rows:
        return 'Your sell list is empty.\n' + HELP
    lines = [f'📋 Sell list — {len(rows)} taken trades']
    for r in rows:
        ctx = json.loads(r['context'])
        fill = f"{r['quantity']} @ ${r['fill_price']:.2f}" if r['fill_price'] else 'fill not recorded'
        state = ' — EXIT ALERT' if r['exit_notice'] else ' — CHECK FAILED' if r['monitor_error'] else ''
        lines.append(f"{r['id']} · [{ctx['expert']}] {ctx['contract']} · {fill}{state}")
    lines.append('Mark closed: /sold TRADE_ID')
    return '\n'.join(lines)


def handle(queue, update, chat):
    """Apply once; cache confirmation before delivery so a failed send is retryable."""
    cb = update.get('callback_query')
    message = cb.get('message', {}) if cb else update.get('message', {})
    if str(message.get('chat', {}).get('id')) != str(chat):
        return None
    text = message.get('text', '').strip()
    if cb:
        if not cb.get('data', '').startswith('taken:'):
            return None
        action, ident, tokens = 'taken', cb['data'][6:], []
    else:
        words = text.split()
        if not words:
            return None
        action = words[0].lower().lstrip('/').split('@')[0]
        if action not in ('taken', 'selllist', 'sold', 'tradehelp'):
            return None
        ident, tokens = None, words[1:]
    with queue.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        prior = db.execute('SELECT response FROM trade_commands WHERE update_id=?', (update['update_id'],)).fetchone()
        if prior:
            return prior['response']
        try:
            if action == 'tradehelp':
                response = HELP
            elif action == 'selllist':
                response = _listing(db)
            else:
                if cb:
                    row = db.execute('SELECT candidate_key FROM trade_messages WHERE message_id=?', (message.get('message_id'),)).fetchone()
                    if not row or trade_id(row['candidate_key']) != ident:
                        raise ValueError('This button is not linked to a recorded trade alert.')
                elif action == 'taken' and message.get('reply_to_message'):
                    ident = _reply_id(db, message)
                else:
                    if not tokens:
                        raise ValueError(HELP)
                    ident, tokens = tokens[0].upper(), tokens[1:]
                if action == 'sold':
                    if tokens:
                        raise ValueError('Use /sold TRADE_ID.')
                    changed = db.execute("UPDATE taken_trades SET status='closed',closed_at=? WHERE id=? AND status!='closed'", (time.time(), ident)).rowcount
                    response = f'✅ {ident} marked closed and removed from the sell list.' if changed else 'No open taken trade with that ID.'
                else:
                    quantity, price, override = _parse_fill(tokens)
                    row = _candidate(db, ident)
                    ctx = json.loads(row['trade_context'] or '{}')
                    if not ctx.get('strategy'):
                        ctx = recover_context(row)
                    if override:
                        ctx['contract'] = override
                    if not ready(ctx):
                        raise ValueError('This alert lacks the saved contract/exit details needed for tracking. Use a new alert with a Taken button.')
                    _validate_contract(ctx['contract'], ctx)
                    old = db.execute('SELECT * FROM taken_trades WHERE id=?', (ident,)).fetchone()
                    if old:
                        if old['status'] == 'closed':
                            raise ValueError('That trade was already marked sold. Use a new entry alert for a new trade.')
                        if override and override != json.loads(old['context'])['contract']:
                            raise ValueError('This ID already tracks a different contract; mark it sold before using a new alert.')
                        if quantity is not None:
                            db.execute('UPDATE taken_trades SET quantity=?,fill_price=? WHERE id=?', (quantity, price, ident))
                        response = f'✅ {ident} already on your sell list.' + (' Fill updated.' if quantity is not None else '')
                    else:
                        db.execute("INSERT INTO taken_trades(id,candidate_key,context,quantity,fill_price,status,taken_at) VALUES (?,?,?,?,?,'open',?)", (ident, row['key'], json.dumps(ctx), quantity, price, time.time()))
                        response = f"✅ Taken — {ctx['contract']}\nTrade ID: {ident}\nAdded to your sell list."
                        response += f'\nFill: {quantity} @ ${price:.2f}' if quantity else f'\nOptional fill: /taken {ident} 2 @ 1.35'
                    response += '\nExit watch: strategy/stock stop on closed 15m bars.\nView: /selllist · Close: /sold ' + ident
        except ValueError as exc:
            response = str(exc)
        db.execute('INSERT INTO trade_commands VALUES (?,?)', (update['update_id'], response))
        return response
