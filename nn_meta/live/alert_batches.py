"""Rank entry notifications across experts before sending at most five per cycle.

Scoring, thresholds, watchlists and paper positions stay with each expert.
The shared durable queue only controls phone notifications.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import math
import json
import os
from pathlib import Path
import sqlite3
import time

import re

# Production alert route: V5 is the only batched legacy expert. V6 paper
# notices are bridged separately after queue dispatch; retired v3/v31/v4
# experts must not hold V5 alert batches open.
EXPERTS = {'v5'}
PROBABILITY_FLOORS = {'v4': 0.51, 'v5': 0.55}
DEFAULT_DB = Path(__file__).parent / '.alert_batches.sqlite3'
TOP_N = 5
BUNDLE_TTL_SECONDS = 3600
# "[v5] SIL BUY PUT" / "ORCL BUY CALL" → (symbol, side); the fallback when a
# legacy payload carries no explicit symbol/side fields.
_TITLE_RE = re.compile(r'^(?:\[\w+\]\s+)?(?P<symbol>[A-Z][A-Z0-9.\-]*)\s+(?P<side>BUY (?:CALL|PUT))\b')


def idea_of(payload):
    """(symbol, side) identity of an entry, or None when it cannot be told.
    2026-09-08 (fix 6): the five slots go to five distinct ideas — a second
    strategy firing on the same symbol and direction is the same trade."""
    symbol, side = payload.get('symbol'), payload.get('side')
    if not (symbol and side):
        m = _TITLE_RE.match(str(payload.get('title', '')))
        if not m:
            return None
        symbol, side = m.group('symbol'), m.group('side')
    return str(symbol).upper(), str(side).upper()


def cycle(now):
    return int(now.timestamp()) // 900 * 900


def enabled(notifier):
    from nn_meta.live.notifier import ConsoleNotifier
    return os.environ.get('NN_META_ALERT_TOP_N') == '5' and not isinstance(notifier, ConsoleNotifier)


class Batches:
    def __init__(self, path=DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS batches (id INTEGER PRIMARY KEY, opened REAL, finalized INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS candidates (key TEXT PRIMARY KEY, batch INTEGER, expert TEXT,
                    score REAL, title TEXT, message TEXT, status TEXT, summary TEXT);
                CREATE TABLE IF NOT EXISTS notices (batch INTEGER PRIMARY KEY, message_id INTEGER);
                CREATE TABLE IF NOT EXISTS reply_state (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS reply_parts (update_id INTEGER, part INTEGER, PRIMARY KEY(update_id,part));
                CREATE TABLE IF NOT EXISTS completed (batch INTEGER, expert TEXT, PRIMARY KEY(batch, expert));
            ''')
            db.execute('INSERT OR IGNORE INTO reply_state VALUES (?,?)', ('enabled_at', str(int(time.time()))))
            db.commit()
            db.execute('BEGIN IMMEDIATE')
            cols = {r[1] for r in db.execute('PRAGMA table_info(candidates)')}
            for col in ('symbol', 'side', 'trade_context', 'trade_ref'):          # additive migration for live queues
                if col not in cols:
                    db.execute(f'ALTER TABLE candidates ADD COLUMN {col} TEXT')

            from nn_meta.live.taken_trades import install, trade_id
            install(db)
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS candidate_trade_ref ON candidates(trade_ref)")
            for row in db.execute("SELECT key FROM candidates WHERE trade_ref IS NULL").fetchall():
                db.execute("UPDATE candidates SET trade_ref=? WHERE key=?", (trade_id(row["key"]), row["key"]))

    def connect(self):
        db = sqlite3.connect(self.path, timeout=60)
        db.row_factory = sqlite3.Row
        return db

    def enqueue(self, payload, key, now=None):
        now = time.time() if now is None else now
        score = payload.get('probability')
        batch = payload.get('alert_cycle')
        expert = payload.get('expert')
        if score is None or not math.isfinite(float(score)) or not 0 <= float(score) <= 1:
            return False  # Leave unrankable legacy entries in their original outbox.
        if not isinstance(batch, int) or expert not in EXPERTS:
            return False
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO batches(id,opened) VALUES (?,?)', (batch,now))
            finalized = db.execute('SELECT finalized FROM batches WHERE id=?',(batch,)).fetchone()[0]
            # Keep sub-floor signals pending so an eligible same-ticker signal
            # can include them as supporting context in the hourly bundle.
            status = ('suppressed_late' if finalized else 'expired'
                      if now >= batch+BUNDLE_TTL_SECONDS else 'pending')
            from nn_meta.live.taken_trades import trade_id
            idea = idea_of(payload)
            db.execute('INSERT OR IGNORE INTO candidates(key,batch,expert,score,title,message,status,summary,symbol,side,trade_context,trade_ref) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                       (key,batch,expert,float(score),payload['title'],payload['message'],status,payload.get('summary',payload['title']),
                        idea[0] if idea else None, idea[1] if idea else None,
                        json.dumps(dict(payload.get('trade_context') or {}, expert=expert, contract=payload.get('contract'))), trade_id(key)))
        return True

    def complete(self, expert, batch):
        if expert not in EXPERTS:
            raise ValueError('unknown expert')
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO completed VALUES (?,?)',(batch,expert))

    def dispatch(self, notifier, now=None):
        now = time.time() if now is None else now
        sent = 0
        # One dispatcher owns sending, including retry selection, across cron overlaps.
        with self.path.with_suffix('.dispatch.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute("UPDATE candidates SET status='suppressed_disabled' WHERE expert != 'v5' AND status IN ('pending','selected')")
                # Thresholding happens after ticker grouping so support signals survive.
                for batch in db.execute('SELECT * FROM batches WHERE finalized=0').fetchall():
                    count = db.execute('SELECT COUNT(*) FROM completed WHERE batch=?',(batch['id'],)).fetchone()[0]
                    # V5 completes each 15-minute scan; the hourly cron controls
                    # when finalized bundles are actually delivered.
                    deadline = min(batch['opened']+300,batch['id']+720)
                    if count < len(EXPERTS) and now < deadline:
                        continue
                    rows = db.execute('SELECT * FROM candidates WHERE batch=? AND status=\'pending\' ORDER BY score DESC,key ASC', (batch['id'],)).fetchall()
                    groups = {}
                    for row in rows:
                        groups.setdefault((row['symbol'] or row['key'],), []).append(row)
                    eligible = [group for group in groups.values()
                                if max(float(row['score']) for row in group) >= PROBABILITY_FLOORS['v5']]
                    eligible.sort(key=lambda group: (-len(group),
                                                     -max(float(row['score']) for row in group),
                                                     str(group[0]['symbol'] or group[0]['key'])))
                    selected_keys = {row['key'] for group in eligible for row in group}
                    for row in rows:
                        members = groups[(row['symbol'] or row['key'],)]
                        status = ('selected' if row['key'] in selected_keys else
                                  'suppressed_probability' if max(float(item['score']) for item in members) < PROBABILITY_FLOORS['v5']
                                  else 'suppressed_rank')
                        db.execute('UPDATE candidates SET status=? WHERE key=?', (status, row['key']))
                    db.execute('UPDATE batches SET finalized=1 WHERE id=?',(batch['id'],))
            with self.connect() as db:
                selected = db.execute("SELECT * FROM candidates WHERE status='selected' ORDER BY batch,score DESC,key ASC").fetchall()
            selected_groups = bundle_groups(selected)
            for group in selected_groups[TOP_N:]:
                with self.connect() as db:
                    db.executemany("UPDATE candidates SET status='suppressed_rank' WHERE key=?", [(row['key'],) for row in group])
            for group in selected_groups[:TOP_N]:
                if all(now >= row['batch'] + BUNDLE_TTL_SECONDS for row in group):
                    with self.connect() as db:
                        db.executemany("UPDATE candidates SET status='expired' WHERE key=?", [(row['key'],) for row in group])
                    continue
                compact = dedupe_signals(group)
                primary = max(compact, key=lambda row: float(row['score']))
                title, message = format_bundle(compact, primary)
                from nn_meta.live.taken_trades import trade_id, ready
                context = json.loads(primary['trade_context'] or '{}')
                message_id = None
                if ready(context) and hasattr(notifier, 'send_trade_alert'):
                    message_id = notifier.send_trade_alert(message, title, trade_id(primary['key']))
                    delivered = message_id is not None
                else:
                    delivered = notifier.send(message, title=title)
                if delivered:
                    with self.connect() as db:
                        db.executemany("UPDATE candidates SET status='sent' WHERE key=?", [(row['key'],) for row in group])
                        if message_id is not None:
                            db.execute("INSERT OR IGNORE INTO trade_messages VALUES (?,?)", (message_id, primary["key"]))
                    sent += 1
        return sent


def _signal_name(row):
    parts = [part.strip() for part in str(row['summary'] or '').split('|')]
    return parts[1] if len(parts) > 1 else str(row['title']).split(':', 1)[0]


def dedupe_signals(group):
    """Keep the strongest occurrence of each strategy/direction in the hour."""
    best = {}
    for row in group:
        key = (_signal_name(row), str(row['side'] or '').upper())
        if key not in best or float(row['score']) > float(best[key]['score']):
            best[key] = row
    return sorted(best.values(), key=lambda row: (-float(row['score']), _signal_name(row)))


def bundle_groups(rows):
    """Group the hourly pool by ticker, retaining call/put conflicts together."""
    groups = {}
    for row in rows:
        groups.setdefault(row['symbol'] or row['key'], []).append(row)
    return sorted(groups.values(), key=lambda group: (
        -len(dedupe_signals(group)), -max(float(row['score']) for row in dedupe_signals(group)),
        str(group[0]['symbol'] or group[0]['key'])))


def _signal_name(row):
    parts = [part.strip() for part in str(row['summary'] or '').split('|')]
    return parts[1] if len(parts) > 1 else str(row['title']).split(':', 1)[0]


def format_bundle(group, primary):
    """Render one ticker proposal, including support and direction conflicts."""
    group = dedupe_signals(group)
    directions = {str(row['side'] or '').upper() for row in group}
    conflict = 'BUY CALL' in directions and 'BUY PUT' in directions
    title = f"{primary['title']} · {len(group)} signals"
    if conflict:
        title = f"⚠️ CALL/PUT CONFLICT · {title}"
    ordered = sorted(group, key=lambda row: (-float(row['score']), _signal_name(row)))
    if conflict:
        lines = []
        for side in ('BUY CALL', 'BUY PUT'):
            members = [row for row in ordered if str(row['side']).upper() == side]
            if members:
                lines.append(f"{side}: " + ' · '.join(
                    f"{_signal_name(row)} P {float(row['score']):.0%}" for row in members))
        proposal = '\n'.join(lines)
        warning = '⚠️ Both directions fired; manual inspection required.'
    else:
        proposal = ' · '.join(
            f"{_signal_name(row)} P {float(row['score']):.0%}" for row in ordered)
        warning = ''
    suffix = f"\n{warning}" if warning else ''
    return title, f"{primary['message']}{suffix}\nsignal proposal: {proposal}"


def select_top(rows, top_n=TOP_N):
    """Keys of the top ``top_n`` rows (already score-ordered) covering distinct
    (symbol, side) ideas; a duplicate idea yields its slot to the next candidate.
    Rows whose idea is unknown are never treated as duplicates of anything."""
    chosen, seen = [], set()
    for row in rows:
        idea = (row['symbol'], row['side']) if row['symbol'] and row['side'] else None
        if idea is not None and idea in seen:
            continue
        chosen.append(row['key'])
        if idea is not None:
            seen.add(idea)
        if len(chosen) >= top_n:
            break
    return chosen


def deliver(payload, key, notifier):
    if enabled(notifier):
        return Batches().enqueue(payload,key)
    return notifier.send(payload['message'], title=payload['title'])


def complete(expert, now, notifier):
    if enabled(notifier):
        Batches().complete(expert,cycle(now))


def main():
    from dotenv import load_dotenv
    from nn_meta.live.notifier import get_notifier
    load_dotenv()
    notifier = get_notifier()
    if not enabled(notifier):
        raise SystemExit('Top-five alert dispatcher is not enabled')
    try:
        queue = Batches()
        with queue.path.with_suffix('.tick.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            from nn_meta.live.v6_alert_bridge import ingest, publish_notices as v6_notices
            v6_spool = os.environ.get('NN_META_V6_ALERT_SPOOL')
            if v6_spool:
                try:
                    ingest(queue, Path(v6_spool))
                except Exception as exc:
                    print(f'V6 import failed ({type(exc).__name__}); existing experts continue', flush=True)
            print(f'Top-five alerts delivered: {queue.dispatch(notifier)}',flush=True)
            if v6_spool:
                try:
                    v6_notices(queue, notifier)
                except Exception as exc:
                    print(f'V6 notice retry pending ({type(exc).__name__}); existing experts continue', flush=True)
            from nn_meta.live.alert_replies import BotAPI, publish_notices, poll_replies
            api = BotAPI()
            publish_notices(queue, api)
            poll_replies(queue, api)
            from nn_meta.live.taken_monitor import send_pending
            send_pending(queue, api)
    except BlockingIOError:
        print('Previous alert dispatcher still running',flush=True)


if __name__ == '__main__':
    main()
