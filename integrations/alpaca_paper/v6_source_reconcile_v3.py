"""Retire expired, never-filled scanner projections after broker reconciliation.

The scanner book contains fractional simulated entries. An initial projection
that never reached the broker must not occupy a slot or demand live risk marks
forever. Preserve its exact row and source events; invent no close or P&L.
Caller holds bridge.lock and .forward.lock across broker reconciliation and write.
"""
from datetime import datetime, timezone
from decimal import Decimal
import json
import sqlite3

from integrations.alpaca_paper.v6_bridge import stamp

TERMINAL={'filled','canceled','expired','rejected'}
POLICY='archive-expired-never-filled-source-v3-contract-reuse'


def retire_unfilled_sources(database, journal, broker_positions, recorded, *, now):
    now=stamp(now)
    rows=[]
    for order in recorded.values():
        saved=journal.get(order['event_id'])
        source=json.loads(saved['payload'])['event']
        rows.append((order,source))
    # A confirmed cancellation between ladder steps is not a completed attempt.
    with journal.connect() as broker:
        has_chains=broker.execute("SELECT 1 FROM sqlite_master WHERE name='step_chains'").fetchone()
        active=[json.loads(r[0])['event'] for r in broker.execute(
            "SELECT payload FROM step_chains WHERE state='active'")] if has_chains else []
        protected={e['position_key'] for e in active}
        protected_contracts={e['contract'] for e in active}
    changes=[]
    with sqlite3.connect(database,timeout=30) as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('''CREATE TABLE IF NOT EXISTS broker_unfilled_sources(
            key TEXT PRIMARY KEY,symbol TEXT,original_state TEXT,original_payload TEXT,
            retired_at TEXT,reason TEXT,evidence TEXT)''')
        for key,symbol,state,payload in db.execute(
                "SELECT key,symbol,state,payload FROM positions WHERE state!='closed'").fetchall():
            if key in protected:
                continue
            position=json.loads(payload)
            # Later legs require their own broker lifecycle; never retire those here.
            if int(position.get('rolls',0))!=0 or position.get('legs'):
                continue
            if position['contract'] in broker_positions or position['contract'] in protected_contracts:
                continue
            contract_orders=[order for order,source in rows if order['contract']==position['contract']]
            if any(order['state'] not in TERMINAL or order['filled_qty'] is None for order in contract_orders):
                continue
            # Historical fills in another signal are harmless only after the
            # contract is flat in both the broker and the reconciled journal.
            net=sum((Decimal(str(o['filled_qty']))*(1 if o['kind']=='entry' else -1)
                     for o in contract_orders), Decimal(0))
            if net != 0:
                continue
            related=[order for order,source in rows if source['position_key']==key]
            if any(order['state'] not in TERMINAL or order['filled_qty'] is None
                   or Decimal(str(order['filled_qty']))!=0 for order in related):
                continue
            sources=[json.loads(r[0]) for r in db.execute(
                'SELECT payload FROM broker_source_entries WHERE key=? AND roll=0',(key,))]
            if len(sources)!=1:raise ValueError('Initial scanner source history is incomplete')
            source=sources[0]
            if (source['contract']!=position['contract'] or source['position_key']!=key
                    or source['event_id']!=key+'|entry|0'):
                raise ValueError('Initial scanner source differs from position')
            deadline=stamp(source.get('signal_close',source['at']))
            if (now-deadline).total_seconds()<=300:
                continue
            evidence=dict(policy=POLICY,broker_position_absent=True,contract_net_fills=str(net),
                contract_orders_terminal=True,all_source_orders_terminal_zero_fill=True,
                contract_orders=[{k:o[k] for k in ('event_id','kind','state','filled_qty')} for o in contract_orders],
                orders=[{k:order[k] for k in ('event_id','state','filled_qty')} for order in related],
                original_source=source,no_broker_close_created=True,no_return_created=True,
                equity_unchanged=True)
            db.execute('INSERT INTO broker_unfilled_sources VALUES(?,?,?,?,?,?,?)',
                (key,symbol,state,payload,now.isoformat(),'broker entry expired without any fill',
                 json.dumps(evidence,sort_keys=True)))
            # Transactional move to an audit table, not deletion of source history.
            db.execute('DELETE FROM positions WHERE key=? AND payload=?',(key,payload))
            changes.append(dict(key=key,contract=position['contract'],reason='expired_unfilled_source'))
    return changes
