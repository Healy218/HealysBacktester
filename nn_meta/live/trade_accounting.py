"""Recorded single-leg long-option cash flows; no quotes or simulated fills."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import re
import time


def amount(value, *, signed=False):
    try:
        n = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('Invalid money amount.') from None
    if not n.is_finite() or abs(n) > Decimal('1000000000') or (not signed and n < 0):
        raise ValueError('Money amounts must be finite and nonnegative.')
    return n


def money(n):
    return f'{n.quantize(Decimal(".01"), rounding=ROUND_HALF_UP):,.2f}'


def install(db):
    db.execute('''CREATE TABLE IF NOT EXISTS taken_accounting_events(
        update_id INTEGER PRIMARY KEY, trade_id TEXT, action TEXT NOT NULL, arguments TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS taken_sales(
        update_id INTEGER PRIMARY KEY, trade_id TEXT NOT NULL, quantity INTEGER NOT NULL,
        premium TEXT NOT NULL, fees TEXT, broker_ref TEXT UNIQUE, recorded_at REAL NOT NULL)''')
    cols = {r[1] for r in db.execute('PRAGMA table_info(taken_trades)')}
    if 'actual_entry_fees' not in cols:
        db.execute('ALTER TABLE taken_trades ADD COLUMN actual_entry_fees TEXT')


def position(db, ident):
    row = db.execute('SELECT * FROM taken_trades WHERE id=?', (ident,)).fetchone()
    if row is None:
        raise ValueError('No tracked trade with that ID.')
    return row


def summary(db, row):
    sales = db.execute('SELECT * FROM taken_sales WHERE trade_id=? ORDER BY update_id', (row['id'],)).fetchall()
    sold = sum(s['quantity'] for s in sales)
    remaining = None if row['quantity'] is None else row['quantity'] - sold
    gross = net = None
    if row['fill_price'] is not None and row['quantity']:
        gross = sum((amount(s['premium']) - amount(row['fill_price'])) * s['quantity'] * 100 for s in sales)
        if row['actual_entry_fees'] is not None and all(s['fees'] is not None for s in sales):
            net = gross - amount(row['actual_entry_fees']) * sold / row['quantity'] - sum(amount(s['fees']) for s in sales)
    return dict(sales=sales, sold=sold, remaining=remaining, gross=gross, net=net)


def report(db, ident):
    row = position(db, ident)
    a = summary(db, row)
    remaining = 'unknown' if a['remaining'] is None else str(a['remaining'])
    lines = [f"{ident} · {json.loads(row['context'])['contract']} · {row['status']}",
             f"Recorded sales: {a['sold']} · remaining by fills: {remaining}"]
    if row['status'] == 'closed' and a['remaining'] != 0:
        lines.append('Closed without complete sale fills; accounting is incomplete.')
    if a['sold']:
        lines.append('Realized gross P/L: ' + ('unknown entry premium' if a['gross'] is None else '$' + money(a['gross'])))
        lines.append('Realized net P/L: ' + ('unknown — record entry and every sale fee' if a['net'] is None else '$' + money(a['net'])))
    for s in a['sales']:
        lines.append(f"Sale {s['update_id']}: {s['quantity']} @ ${s['premium']} · fees "
                     + ('unknown' if s['fees'] is None else '$' + s['fees'])
                     + (f" · ref {s['broker_ref']}" if s['broker_ref'] else ''))
    return '\n'.join(lines)


def sell(db, ident, tokens, update_id):
    row = position(db, ident)
    if not tokens:
        if row['status'] == 'closed':
            return 'No open taken trade with that ID.'
        db.execute("UPDATE taken_trades SET status='closed',closed_at=? WHERE id=?", (time.time(), ident))
        return f'✅ {ident} marked closed and removed from the sell list. Sale fills not recorded; P/L incomplete.'
    match = re.fullmatch(r'(\d+)\s*@\s*\$?((?:\d+(?:\.\d+)?|\.\d+))(?:\s+fees\s+\$?([\d.]+))?(?:\s+ref\s+([A-Za-z0-9_.:-]{1,100}))?', ' '.join(tokens))
    if not match:
        raise ValueError('Use /sold ID quantity @ premium [fees TOTAL_DOLLARS] [ref BROKER_FILL_ID].')
    qty, premium = int(match[1]), amount(match[2])
    fee = None if match[3] is None else str(amount(match[3]))
    ref = match[4]
    if ref:
        old = db.execute('SELECT * FROM taken_sales WHERE broker_ref=?', (ref,)).fetchone()
        if old:
            if old['trade_id'] == ident and old['quantity'] == qty and amount(old['premium']) == premium and (old['fees'] is None and fee is None or old['fees'] is not None and fee is not None and amount(old['fees']) == amount(fee)):
                return 'Sale already recorded.\n' + report(db, ident)
            raise ValueError('Broker reference already used with different fill details.')
    a = summary(db, row)
    if not 1 <= qty <= 100000 or a['remaining'] is None or qty > a['remaining']:
        raise ValueError('Record the entry quantity first; sale quantity must be positive and cannot exceed remaining contracts.')
    # Permit completing the details of a legacy /sold closure, without reopening it.
    remaining = a['remaining'] - qty
    db.execute('INSERT INTO taken_sales VALUES (?,?,?,?,?,?,?)', (update_id, ident, qty, str(premium), fee, ref, time.time()))
    if remaining == 0:
        db.execute("UPDATE taken_trades SET status='closed',closed_at=COALESCE(closed_at,?) WHERE id=?", (time.time(), ident))
    return '✅ Sale recorded.\n' + report(db, ident)


def reconcile(db, records):
    """Compare normalized broker records read-only; exact Decimal comparisons.

    Each record: trade_id, contract, entry_quantity, entry_price, entry_fees,
    remaining_quantity, sales [{quantity, premium, fees, broker_ref}].
    A match establishes agreement with supplied records, not broker authentication.
    """
    results = []
    seen = set()
    for record in records:
        ident = record['trade_id'].upper()
        if ident in seen:
            raise ValueError('Duplicate trade_id in broker records.')
        seen.add(ident)
        row = position(db, ident)
        a = summary(db, row)
        differences = []
        checks = dict(contract=json.loads(row['context'])['contract'], entry_quantity=row['quantity'],
                      entry_price=row['fill_price'], entry_fees=row['actual_entry_fees'], remaining_quantity=a['remaining'])
        for key, value in checks.items():
            expected = record[key]
            if value is None or expected is None:
                differences.append(key + ': missing')
            elif key == 'contract':
                if value != expected:
                    differences.append(key + ': mismatch')
            elif amount(value) != amount(expected):
                differences.append(key + ': mismatch')
        def fills(items):
            result = []
            refs = set()
            for item in items:
                ref = item['broker_ref']
                if not ref or ref in refs or item['fees'] is None:
                    raise ValueError('Reconciliation requires unique broker references and actual sale fees.')
                refs.add(ref)
                quantity = amount(item['quantity'])
                if quantity <= 0 or quantity != quantity.to_integral_value():
                    raise ValueError('Broker sale quantity must be a positive integer.')
                result.append((ref, quantity, amount(item['premium']), amount(item['fees'])))
            return sorted(result)
        try:
            if fills(a['sales']) != fills(record['sales']):
                differences.append('sales: mismatch')
        except ValueError as exc:
            differences.append(str(exc))
        if row['status'] == 'closed' and a['remaining'] != 0:
            differences.append('closed status lacks complete sale fills')
        results.append(dict(trade_id=ident, matched=not differences, differences=differences))
    return results
