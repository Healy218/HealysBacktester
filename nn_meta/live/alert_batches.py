"""Rank entry notifications across experts before sending at most five per cycle.

Scoring, thresholds, watchlists and paper positions stay with each expert.
The shared durable queue only controls phone notifications.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import math
import os
from pathlib import Path
import sqlite3
import time

import re

EXPERTS = {'v3', 'v31', 'v4', 'v5'}
PROBABILITY_FLOORS = {'v4': 0.51, 'v5': 0.55}
DEFAULT_DB = Path(__file__).parent / '.alert_batches.sqlite3'
TOP_N = 5
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
            cols = {r[1] for r in db.execute('PRAGMA table_info(candidates)')}
            for col in ('symbol', 'side'):          # additive migration for live queues
                if col not in cols:
                    db.execute(f'ALTER TABLE candidates ADD COLUMN {col} TEXT')

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
            status = ('suppressed_probability' if float(score) <= PROBABILITY_FLOORS.get(expert, -1)
                      else 'suppressed_late' if finalized else 'expired' if now >= batch+900 else 'pending')
            idea = idea_of(payload)
            db.execute('INSERT OR IGNORE INTO candidates(key,batch,expert,score,title,message,status,summary,symbol,side) VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (key,batch,expert,float(score),payload['title'],payload['message'],status,payload.get('summary',payload['title']),
                        idea[0] if idea else None, idea[1] if idea else None))
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
                for expert, floor in PROBABILITY_FLOORS.items():
                    db.execute("UPDATE candidates SET status='suppressed_probability' WHERE expert=? AND score<=? AND status IN ('pending','selected','suppressed_rank','suppressed_late')", (expert,floor))
                for batch in db.execute('SELECT * FROM batches WHERE finalized=0').fetchall():
                    count = db.execute('SELECT COUNT(*) FROM completed WHERE batch=?',(batch['id'],)).fetchone()[0]
                    # Wait for all experts, or at most five minutes after the first
                    # result; never wait beyond twelve minutes after bar close.
                    deadline = min(batch['opened']+300,batch['id']+720)
                    if count < len(EXPERTS) and now < deadline:
                        continue
                    winners = select_top(db.execute("SELECT key,symbol,side FROM candidates WHERE batch=? AND status='pending' ORDER BY score DESC,key ASC",(batch['id'],)).fetchall())
                    db.execute("UPDATE candidates SET status='suppressed_rank' WHERE batch=? AND status='pending'",(batch['id'],))
                    for winner in winners:
                        db.execute("UPDATE candidates SET status='selected' WHERE key=?",(winner,))
                    db.execute('UPDATE batches SET finalized=1 WHERE id=?',(batch['id'],))
            with self.connect() as db:
                selected = db.execute("SELECT * FROM candidates WHERE status='selected' ORDER BY batch,score DESC,key ASC").fetchall()
            for row in selected:
                if now >= row['batch']+900:
                    with self.connect() as db:
                        db.execute("UPDATE candidates SET status='expired' WHERE key=?",(row['key'],))
                    continue
                if notifier.send(row['message'],title=row['title']):
                    with self.connect() as db:
                        db.execute("UPDATE candidates SET status='sent' WHERE key=?",(row['key'],))
                    sent += 1
        return sent


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
            print(f'Top-five alerts delivered: {queue.dispatch(notifier)}',flush=True)
            from nn_meta.live.alert_replies import BotAPI, publish_notices, poll_replies
            api = BotAPI()
            publish_notices(queue, api)
            poll_replies(queue, api)
    except BlockingIOError:
        print('Previous alert dispatcher still running',flush=True)


if __name__ == '__main__':
    main()
