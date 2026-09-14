"""Consume immutable V6 paper-event files through the existing alert process.

No model import, no broker actions. V6 reports its already allocated paper
positions alongside the older experts; their phone-ranking cycle stays frozen.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time


def tables(queue):
    with queue.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS v6_notices(key TEXT PRIMARY KEY, payload TEXT, status TEXT, created_at TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS v6_imports(key TEXT PRIMARY KEY, sha256 TEXT, imported_at REAL)')


def ingest(queue, spool, now=None):
    now = time.time() if now is None else now
    tables(queue)
    count = 0
    for path in sorted(Path(spool).glob('*.json')):
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        event = json.loads(content)
        key = event['key']
        if (event.get('schema') != 'v6-forward-alert-v1' or not key.startswith('v6|')
                or event.get('kind') not in ('entry', 'notice') or event.get('experimental') is not True):
            raise ValueError('invalid V6 paper alert event')
        with queue.connect() as db:
            prior = db.execute('SELECT sha256 FROM v6_imports WHERE key=?',(key,)).fetchone()
        if prior:
            if prior[0] != digest:
                raise ValueError('V6 event changed after import')
            continue
        payload = event['payload']
        if event['kind'] == 'entry' and payload.get('expert') != 'v6':
            raise ValueError('V6 paper entry belongs to another expert')
        if not str(payload.get('title','')).startswith('[v6]') or not payload.get('message'):
            raise ValueError('V6 paper notice is missing its identity or message')
        with queue.connect() as db:
            db.execute('INSERT OR IGNORE INTO v6_notices VALUES (?,?,?,?)',
                (key,json.dumps(payload),'pending',event['created_at']))
        with queue.connect() as db:
            db.execute('INSERT OR IGNORE INTO v6_imports VALUES (?,?,?)',(key,digest,now))
        count += 1
    return count


def publish_notices(queue, notifier):
    tables(queue)
    with queue.connect() as db:
        events = db.execute("SELECT * FROM v6_notices WHERE status='pending' ORDER BY created_at,key").fetchall()
    sent=0
    for event in events:
        payload=json.loads(event['payload'])
        if notifier.send(payload['message'],title=payload['title']):
            with queue.connect() as db:
                db.execute("UPDATE v6_notices SET status='sent' WHERE key=?",(event['key'],))
            sent+=1
    return sent
