"""Parity of the ETFE label kernel with the per-second synthetic Scheduler, plus edge cases."""
import datetime as dt
import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nn_meta.etfe import label_kernel as k
from nn_meta.etfe.expiry_ledger import settlement_clock
from nn_meta.etfe.integration_ledger import Scheduler

ROOT=Path(__file__).resolve().parents[1]
CASES=json.loads((ROOT/'docs/specs/ETFE_INTEGRATION_FIXTURES_20261005.json').read_text())['cases']
NS=k.NS


def ns(x):
    return pd.Timestamp(x).value


def market_from_tape(tape):
    base,life=tape['base'],tape['lifecycle'];lo,hi=ns(tape['start']),ns(tape['end'])
    contracts={};by_expiry={}
    for c,b in base['contracts'].items():
        terms=life['terms'][c];right='call' if b['right']=='C' else 'put';exp=dt.date.fromisoformat(b['expiration_date'])
        avail=pd.Timestamp(b['known_at']).tz_convert('America/New_York').date()+dt.timedelta(days=1)
        contracts[c]=(b['symbol'],right,exp,float(terms['strike']),avail)
        by_expiry.setdefault((b['symbol'],right,exp),[]).append((float(terms['strike']),c))
    bars={}
    for c in base['contracts']:
        rows=sorted(tape['bars'].get(c,[]),key=lambda r:r['t'])
        bars[c]=k.Bars(np.array([ns(r['t']) for r in rows],np.int64),np.array([r['vw'] for r in rows],float),
            np.array([r['v'] for r in rows],np.int64),np.array([r['n'] for r in rows],np.int64),lo,hi)
    quotes={}
    for sym,rows in tape['quotes'].items():
        rows=sorted(rows,key=lambda r:r['t'])
        quotes[sym]=k.Quotes(np.array([ns(r['t']) for r in rows],np.int64),np.array([r['bid'] for r in rows],float),
            np.array([r['ask'] for r in rows],float),np.array([r['bid_size'] for r in rows],np.int64),
            np.array([r['ask_size'] for r in rows],np.int64),[(lo,hi)],np.array([ns(r['available_at']) for r in rows],np.int64))
    any_symbol=next(iter(life['stock_sessions']))
    sessions={dt.date.fromisoformat(d):(ns(a),ns(b)) for d,(a,b) in life['stock_sessions'][any_symbol].items()}
    cal=life['calendar'];days=[dt.date.fromisoformat(d) for d in cal['business_dates']]
    equity={}
    for d in cal['business_dates']:
        due=settlement_clock(d,cal)
        if due:equity[dt.date.fromisoformat(d)]=pd.Timestamp(due).tz_convert('America/New_York').date()
    refs={}
    for c,rows in tape['exercises'].items():
        b=base['contracts'][c];refs[b['symbol'],dt.date.fromisoformat(b['expiration_date'])]=rows[-1]['price']
    return k.Market(bars=bars,quotes=quotes,contracts=contracts,by_expiry={x:sorted(v) for x,v in by_expiry.items()},
        sessions=sessions,equity_settle=equity,settle_days=days,references=refs,weekly=set())


def single(tape,pid):
    t=deepcopy(tape);t['proposals']=[p for p in t['proposals'] if p['id']==pid]
    t['strategy_exits']=[e for e in t['strategy_exits'] if e['proposal_id']==pid];return t


@pytest.mark.parametrize('case',CASES,ids=[c['id'] for c in CASES])
def test_kernel_matches_scheduler_per_proposal(case):
    tape=case['tape']
    for p in tape['proposals']:
        one=single(tape,p['id']);sched=Scheduler(one);report=sched.run();ref=report['paths'][p['id']]
        fills=[e for e in sched.ledger.events if e['kind']=='fill' and e['side']=='buy' and e['proposal_id']==p['id']]
        assert fills,'reference never entered'
        contract=fills[0]['contract']
        exits=[ns(e['at']) for e in one['strategy_exits']]
        kernel=k.Kernel(market_from_tape(one),dict(lag_seconds=1,quote_lag_seconds=0,end_ns=ns(tape['end'])))
        got=kernel.run(contract,ns(p['signal_at']),min(exits) if exits else None,p['target'])
        expected={'open':'right_censored_end'}.get(ref['status'],ref['status'])
        assert got.status==expected,(case['id'],got.status,got.reason,ref)
        assert got.debit==-fills[0]['cash_cents'] if fills[0]['cash_cents']<0 else got.debit==fills[0]['cash_cents']
        if ref['status']=='settled':
            assert got.pnl==ref['synthetic_pnl_cents'],(case['id'],got.pnl,ref['synthetic_pnl_cents'],got.events)


def test_inline_gate_matches_purchase_policy():
    from nn_meta.etfe.purchase_policy_v2 import check_purchase
    mk=k.Market(bars={},quotes={},contracts={'X':('SPY','call',dt.date(2024,5,24),500.0,dt.date(2024,5,10))},by_expiry={},
        sessions={dt.date(2024,5,24):(ns('2024-05-24T13:30Z'),ns('2024-05-24T20:00Z'))},equity_settle={},settle_days=[],references={},weekly={'SPY'})
    kern=k.Kernel(mk)
    for attempt in ('2024-05-18T15:00Z','2024-05-19T15:00Z','2024-05-24T19:44Z','2024-05-24T19:45Z'):
        for target in (0,1,2,4,5,7):
            ok=check_purchase('2024-05-24',attempt,target=target,weekly_eligible=True)['dte_eligible']
            reason=kern.gate('X',ns(attempt),target)
            if not ok:assert reason in ('target_not_enabled','outside_0_to_5_calendar_dte')
            elif attempt.endswith('19:45Z'):assert reason=='expiry_exit_cutoff_reached'
            else:assert reason is None


def test_reference_is_newest_bar_only_and_fresh():
    t0=ns('2024-05-24T14:00Z')
    bars=k.Bars(np.array([t0,t0+2*k.MINUTE],np.int64),np.array([1.,1.]),np.array([500,500],np.int64),np.array([5,5],np.int64),0,2*t0)
    kern=k.Kernel(k.Market({}, {}, {}, {}, {}, {}, [], {}, set()))
    assert kern.ref(bars,t0+k.MINUTE+NS)==0           # available end + 1 s
    assert kern.ref(bars,t0+2*k.MINUTE)==0            # still fresh at end + 60 s
    assert kern.ref(bars,t0+2*k.MINUTE+NS) is None    # stale: no backward search past freshness
    assert kern.ref(bars,t0+3*k.MINUTE+NS)==1


def test_fill_rounding_follows_reference_operation_order():
    kern=k.Kernel(k.Market({}, {}, {}, {}, {}, {}, [], {}, set()))
    # 1 x 100 x 4.70: gross+fee+slip = 470.70500000000004 -> 470.71 (a fused 1.0015 factor gives 470.705 -> 470.70)
    assert kern.fill(k.Path(),'buy',1,4.7)==47071
    assert kern.fill(k.Path(),'sell',1,4.7)==cents_ref(470.0-0.47-0.235)


def cents_ref(x):
    from nn_meta.etfe.execution_ledger import cents
    return cents(x)


def test_expiry_override_moves_close_and_reference():
    d8,d9=dt.date(2025,1,8),dt.date(2025,1,9)
    mk=k.Market(bars={},quotes={},contracts={'X':('SPY','call',d9,500.0,dt.date(2025,1,2))},by_expiry={},
        sessions={d8:(ns('2025-01-08T14:30Z'),ns('2025-01-08T21:00Z'))},equity_settle={d8:d9},settle_days=[d8,d9],
        references={('SPY',d8):501.0},weekly=set(),expiry_overrides={d9:d8})
    kern=k.Kernel(mk)
    assert kern.expiry_close(d9)==ns('2025-01-08T21:00Z')
    assert kern.gate('X',ns('2025-01-08T20:45Z'),1)=='expiry_exit_cutoff_reached'
    assert kern.gate('X',ns('2025-01-08T15:00Z'),1) is None


def test_stressed_bars_remove_tenth_and_edge_blocks_chronologically():
    from nn_meta.etfe import label_build as b
    day=dt.date(2024,5,24);op,cl=ns('2024-05-24T13:30Z'),ns('2024-05-24T20:00Z')
    starts=np.array([op+i*k.MINUTE for i in range(390)],np.int64);n=len(starts)
    bars={'X':k.Bars(starts,np.ones(n),np.full(n,10,np.int64),np.ones(n,np.int64),op,cl)}
    mk=k.Market(bars,{}, {}, {}, {day:(op,cl)},{},[],{},set())
    tenth=b.stressed_bars(mk,dict(remove_every_tenth=True,remove_edge_blocks=[]))['X']
    assert len(tenth.start)==390-39 and starts[9] not in set(tenth.start) and starts[10] in set(tenth.start)
    first=b.stressed_bars(mk,dict(remove_every_tenth=False,remove_edge_blocks=[['first',1]]))['X']
    assert set(starts)-set(first.start)=={starts[i] for i in range(5,10)}
    last=b.stressed_bars(mk,dict(remove_every_tenth=False,remove_edge_blocks=[['last',0]]))['X']
    assert set(starts)-set(last.start)=={starts[i] for i in range(360,365)}
