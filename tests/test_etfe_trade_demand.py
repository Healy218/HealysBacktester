import pandas as pd
import pytest
from nn_meta.etfe.trade_demand import jobs_from_demand


def demand(symbol='SPY240119C00475000',a=1705674600000000000,b=1705674660000000000):
    return dict(symbol=symbol,route='option_trades',intervals=[[a,b]],uncaptured_intervals=[[a,b]])


def test_exact_batched_half_open_demand():
    d=demand();other=demand('QQQ240119P00405000')
    jobs,edges=jobs_from_demand({'physical':[d,other]})
    assert len(jobs)==1 and len(edges)==2
    p=jobs[0]['params'];assert 'feed' not in p and p['limit']==10000
    assert pd.Timestamp(p['start']).value==d['intervals'][0][0]
    assert pd.Timestamp(p['end']).value==d['intervals'][0][1]-1
    assert set(p['symbols'].split(','))=={d['symbol'],other['symbol']}


def test_different_intervals_not_widened_and_bar_demand_skipped():
    a=demand();b=demand('QQQ240119P00405000',b=a['intervals'][0][1]+60_000_000_000)
    c=dict(demand(),route='option_bars')
    jobs,edges=jobs_from_demand({'physical':[a,b,c]})
    assert len(jobs)==2 and len(edges)==2


def test_duplicate_or_outside_or_unaligned_demand_rejected():
    d=demand()
    with pytest.raises(ValueError,match='Duplicate'):jobs_from_demand({'physical':[d,d]})
    with pytest.raises(ValueError,match='Overlapping'):
        jobs_from_demand({'physical':[d,demand(b=d['intervals'][0][1]+60_000_000_000)]})
    d['uncaptured_intervals'][0][0]-=60_000_000_000
    with pytest.raises(ValueError,match='outside'):jobs_from_demand({'physical':[d]})
    with pytest.raises(ValueError,match='Aligned'):jobs_from_demand({'physical':[demand(a=1,b=2)]})


def test_symbol_batch_cap():
    d={'physical':[demand(f'SPY240119C{strike:08d}') for strike in range(100000,100101)]}
    jobs,edges=jobs_from_demand(d)
    assert len(jobs)==2 and len(edges)==101
    assert max(len(j['params']['symbols'].split(',')) for j in jobs)==100


@pytest.mark.parametrize('exhausted',['requests','seconds','invocations'])
def test_total_study_budget_cannot_reset_on_resume(tmp_path,monkeypatch,exhausted):
    import json
    from nn_meta.etfe import trade_demand
    runs=tmp_path/'runs';runs.mkdir()
    (runs/'prior.json').write_text(json.dumps(dict(requests_this_run=512 if exhausted=='requests' else 1,
        elapsed_seconds=1800 if exhausted=='seconds' else 1)))
    limits=dict(max_requests=512,max_active_seconds=1800,max_invocations=1 if exhausted=='invocations' else 8)
    monkeypatch.setattr(trade_demand,'verify',lambda root:dict(parent=dict(study_limits=limits)))
    monkeypatch.setattr(trade_demand,'capture',lambda *a,**kw:pytest.fail('Exhausted budget must not make a capture call'))
    with pytest.raises(ValueError,match='budget exhausted'):trade_demand.run(tmp_path,object())
