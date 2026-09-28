"""Version 4 PAPER dispatcher; step orders with complete sell liquidity slicing."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,prefix=path.name+'.',delete=False) as stream:
        stream.write(json.dumps(value,indent=2,sort_keys=True,default=str)+'\n')
        stream.flush()
        os.fsync(stream.fileno())
        temp=Path(stream.name)
    temp.chmod(0o600)
    temp.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(state, *, require_fresh=False):
    m = read(state/'paper-restart.json')
    if (m.get('schema')!='v6-alpaca-paper-restart-prepared-v1' or
            m.get('historical_positions_imported') is not False or
            not m.get('activated_at') or not m.get('scanner_enabled')):
        raise ValueError('paper runtime is not activated')
    required = ('integrations/alpaca_paper/v6_step_slices.py',
                'integrations/alpaca_paper/v6_bridge_v3.py',
                'integrations/alpaca_paper/v6_pricing_v3.py',
                'scripts/run_v6_alpaca_runtime_v4.py')
    if (m.get('execution_policy') != 'midpoint-step-2.5-5-7.5-10pct-v3'
            or any(rel not in m['bridge_runtime_sha256'] for rel in required)):
        raise ValueError('version 3 execution policy is not admitted in the runtime manifest')
    old = Path(m['old_state'])
    if state.resolve()==old.resolve() or state.resolve().is_relative_to(old.resolve()):
        raise ValueError('paper state must be isolated from historical state')
    frozen = old.parents[2]
    activation = read(state/'activation.json')
    for rel,digest in activation['runtime_sha256'].items():
        if sha(frozen/rel)!=digest:
            raise ValueError('frozen V6 runtime hash mismatch: '+rel)
    for rel,digest in m['bridge_runtime_sha256'].items():
        if sha(ROOT/rel)!=digest:
            raise ValueError('paper bridge runtime hash mismatch: '+rel)
    index = read(Path(m['data_index_source']))
    if index['release_sha256']!=m['release_sha256'] or sha(Path(index['path'])/'manifest.json')!=index['sha256']:
        raise ValueError('current V6 data index failed verification')
    from nn_meta.session_calendar import SessionCalendar
    from zoneinfo import ZoneInfo
    data_manifest=read(Path(index['path'])/'manifest.json')
    calendar_path=Path(index['path'])/'calendar.json'
    if sha(calendar_path)!=data_manifest['files']['calendar.json']:
        raise ValueError('current V6 calendar failed verification')
    calendar=SessionCalendar(read(calendar_path))
    today=datetime.now(ZoneInfo('America/New_York')).date().isoformat()
    calendar.bounds(today)
    prior=max(day for day in calendar.sessions if day<today)
    if require_fresh and data_manifest['through']<prior:
        raise ValueError('V6 daily data is stale; required prior session '+prior)
    save(state/'data-index.json',index)
    return m,index,frozen


def clients(env):
    from dotenv import dotenv_values
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical.option import OptionHistoricalDataClient
    values = dotenv_values(env)
    key,secret = values.get('ALPACA_PAPER_API_KEY'),values.get('ALPACA_PAPER_API_SECRET')
    if not key or not secret:
        raise ValueError('dedicated paper credentials missing')
    return TradingClient(key,secret,paper=True),OptionHistoricalDataClient(key,secret)


def poll(state, m, index, env, *, preview=False):
    from integrations.alpaca_paper.v6_step_slices import Journal,events_from_fresh_state,process_events,reconcile,stamp
    from integrations.alpaca_paper.v6_runtime import risk_events
    from nn_meta.session_calendar import SessionCalendar
    trading,data = clients(env)
    journal = Journal(state/'broker-orders.sqlite3')
    account,positions,orders = reconcile(journal,trading,expected_fingerprint=m['account_fingerprint'],allow_pending=True)
    calendar_path = Path(index['path'])/'calendar.json'
    data_manifest = read(Path(index['path'])/'manifest.json')
    if sha(calendar_path)!=data_manifest['files']['calendar.json']:
        raise ValueError('calendar hash mismatch')
    calendar=SessionCalendar(read(calendar_path))
    clock = trading.get_clock()
    now = datetime.now(timezone.utc)
    # Alpaca's stock clock closes at 16:00; eligible ETF options can still
    # need their 16:00 expiry exit during the following fifteen minutes.
    from zoneinfo import ZoneInfo
    from nn_meta.live.v6_option_sessions import LATE_CLOSE
    from options.data.provider import parse_occ_symbol
    eastern=now.astimezone(ZoneInfo('America/New_York'))
    late_positions=any(parse_occ_symbol(s)[0] in LATE_CLOSE for s in positions)
    bounds=calendar.bounds(eastern.date().isoformat())
    closing=bounds[1].to_pydatetime().replace(tzinfo=timezone.utc) if bounds else None
    late_window=bool(late_positions and closing and closing<=now<closing+timedelta(minutes=15))
    if not clock.is_open and not late_window:
        return {'status':'market_closed','next_open':str(clock.next_open),
                'positions':len(positions),'orders':len(orders), 'paper_only':True}
    events = events_from_fresh_state(state/'portfolio.sqlite3',activated_at=stamp(m['activated_at']))
    risk = risk_events(journal,positions,data,events,calendar)
    # Mirror only the broker's stop instruction into the prospective simulator;
    # its price projection stays separate from actual broker fills.
    with sqlite3.connect(state/'portfolio.sqlite3') as db:
        db.execute('BEGIN IMMEDIATE')
        for event in risk:
            if event['reason']!='broker premium stop':
                continue
            row=db.execute('SELECT payload FROM positions WHERE key=? AND state=?',
                           (event['position_key'],'open')).fetchone()
            if row:
                position=json.loads(row[0])
                if position['contract']==event['contract']:
                    position.update(state='exit_due',trigger_at=event['trigger_at'],
                                    trigger_reason=event['reason'])
                    db.execute('UPDATE positions SET state=?,payload=? WHERE key=?',
                               ('exit_due',json.dumps(position,sort_keys=True),event['position_key']))
    # Exits receive priority. The bridge independently verifies prerequisite
    # roll closes and skips expired/superseded source entries.
    events = sorted(risk + events,key=lambda e:(e['kind']!='close',e['at'],e['event_id']))
    if not clock.is_open:
        events=[e for e in events if e['kind']=='close']
    if preview or not m.get('order_submission_enabled'):
        preview_result = process_events(events,journal=journal,trading=trading,data=data,
                                        expected_fingerprint=m['account_fingerprint'])
        save(state/'latest-preview.json',{'at':datetime.now(timezone.utc).isoformat(),
                                        'events':len(events),'outcomes':preview_result})
        return {'status':'preview','outcomes':preview_result}
    # Each submitted order carries its fresh validated plan in the durable journal.
    outcomes = process_events(events,journal=journal,trading=trading,data=data,
                              expected_fingerprint=m['account_fingerprint'],submit=True)
    return {'status':'complete','outcomes':outcomes,'paper_only':True,
            'execution_policy':'midpoint-step-2.5-5-7.5-10pct-v3',
            'positions_before':len(positions),'options_buying_power':str(account.options_buying_power)}


def scan(state,m,index,frozen,env,workers):
    # Every scan reads the producer's latest immutable pointer. The old account
    # portfolio is never opened by this scanner.
    release = frozen/'deploy/v6/releases/v6-cash-repair-20260913'
    command=[sys.executable,'-m','scripts.run_v6_forward','--release',str(release),
             '--anchor',m['release_sha256'],'--data-index',str(state/'data-index.json'),
             '--state',str(state),'--env',str(env),'--workers',str(workers)]
    subprocess.run(command,cwd=frozen,check=True,timeout=570)
    return read(state/'status.json')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['scan','poll','check'])
    p.add_argument('--state',type=Path,required=True)
    p.add_argument('--env',type=Path,default=ROOT/'.env')
    p.add_argument('--workers',type=int,default=1)
    p.add_argument('--preview',action='store_true')
    a=p.parse_args();state=a.state.resolve()
    lockname='scanner-dispatch.lock' if a.action=='scan' else 'bridge.lock'
    with (state/lockname).open('a+') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        report={'checked_at':datetime.now(timezone.utc).isoformat(),'action':a.action}
        target=state/('scanner-dispatch-status.json' if a.action=='scan' else 'broker-status.json')
        try:
            m,index,frozen=validate(state,require_fresh=a.action=='scan')
            if a.action=='scan':
                result=scan(state,m,index,frozen,a.env.resolve(),a.workers)
            else:
                result=poll(state,m,index,a.env.resolve(),preview=a.preview or a.action=='check')
            report.update(result)
        except Exception as exc:
            report.update(status='blocked',error=type(exc).__name__+': '+str(exc))
            save(target,report)
            raise
        save(target,report)
        print(json.dumps(report,default=str,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
