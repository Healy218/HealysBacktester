"""Durable source legs and broker-native risk for the fresh paper deployment."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sqlite3

from integrations.alpaca_paper.v6_bridge import stamp, quote_dict
from integrations.alpaca_paper.v6_pricing import mark_limit


def install_leg_capture(database: Path) -> None:
    """SQLite triggers commit each entry alongside the scanner's own transaction."""
    with sqlite3.connect(database) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS broker_source_entries (
            key TEXT NOT NULL, roll INTEGER NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY(key,roll))''')
        body = '''INSERT INTO broker_source_entries VALUES (
            NEW.key, json_extract(NEW.payload,'$.rolls'),
            json_object('event_id',NEW.key||'|entry|'||json_extract(NEW.payload,'$.rolls'),
              'kind','entry','position_key',NEW.key,
              'contract',json_extract(NEW.payload,'$.contract'),
              'at',json_extract(NEW.payload,'$.entry_quote.received_at'),
              'signal_close',CASE WHEN json_extract(NEW.payload,'$.rolls')=0 THEN
                datetime(json_extract(NEW.payload,'$.entry_ts'),'+15 minutes')||'+00:00'
                ELSE json_extract(NEW.payload,'$.entry_quote.received_at') END,
              'size_fraction',json_extract(NEW.payload,'$.size_fraction'),
              'roll',json_extract(NEW.payload,'$.rolls')));'''
        db.executescript('''CREATE TRIGGER IF NOT EXISTS broker_capture_initial AFTER INSERT ON positions
            BEGIN ''' + body + ''' END;
            CREATE TRIGGER IF NOT EXISTS broker_capture_roll AFTER UPDATE ON positions
            WHEN json_extract(NEW.payload,'$.rolls') != json_extract(OLD.payload,'$.rolls')
            BEGIN ''' + body + ''' END;''')


def risk_events(journal, positions, data, events, calendar, *, now=None):
    """Persist stops from actual fill basis; do not lose an exit on a rebound."""
    from alpaca.data.enums import OptionsFeed
    from alpaca.data.requests import OptionSnapshotRequest
    from nn_meta.live.v6_option_sessions import expiry_cutoff
    fixed_now = now
    now = now or datetime.now(timezone.utc)
    with journal.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS risk_events (event_id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
        saved = [json.loads(r[0]) for r in db.execute('SELECT payload FROM risk_events')]
    for symbol, position in positions.items():
        entry = next((e for e in reversed(events) if e['kind']=='entry' and e['contract']==symbol), None)
        if entry is None:
            raise ValueError('broker position has no durable scanner entry')
        if any(e['contract']==symbol and e['position_key']==entry['position_key'] for e in saved):
            continue
        cutoff = expiry_cutoff(symbol, calendar).to_pydatetime()
        reason = None
        if now >= cutoff:
            reason = 'broker expiry cutoff'
        else:
            snapshot = data.get_option_snapshot(OptionSnapshotRequest(
                symbol_or_symbols=symbol, feed=OptionsFeed.OPRA))[symbol]
            received = fixed_now or datetime.now(timezone.utc)
            quote = mark_limit(quote_dict(snapshot, received_at=received), now=received, after=stamp(entry['at']))
            basis = Decimal(str(position.avg_entry_price))
            if basis <= 0:
                raise ValueError('invalid broker entry basis')
            if Decimal(quote['raw_mark']) <= basis * Decimal('0.875'):
                reason = 'broker premium stop'
        if reason:
            event = {'event_id': entry['event_id']+'|broker-risk', 'kind':'close',
                     'position_key':entry['position_key'], 'contract':symbol,
                     'at':now.isoformat(), 'trigger_at':now.isoformat(), 'reason':reason}
            with journal.connect() as db:
                db.execute('INSERT OR IGNORE INTO risk_events VALUES (?,?)',
                           (event['event_id'],json.dumps(event,sort_keys=True)))
            saved.append(event)
    return saved
