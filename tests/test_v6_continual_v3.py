import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import requests

from incubator.recovery_v6.data import candidate_key, candidate_batch, proposal_records
from incubator.recovery_v6.market import RetrySession, RetryingTicks
from incubator.recovery_v6.inheritance import ParentArtifacts
from incubator.continual.storage import seal, sha


def test_colliding_exit_trades_keep_independent_candidate_identity_and_horizons(monkeypatch):
    from nn_meta import proposals,config
    from portfolio import simulator
    from incubator.continual.data import candidate_key as original_key
    index=pd.date_range('2026-09-01 13:30',periods=4,freq='15min')
    bars=pd.DataFrame({'Close':[100,101,102,103]},index=index)
    signals=pd.DataFrame(True,index=index,columns=['one'])
    monkeypatch.setattr(proposals,'single_signals',lambda *a:[signals,None,None,None])
    monkeypatch.setattr(config,'WINDOW_START','2026-09-01')
    records=pd.DataFrame(dict(entry_idx=[1,1],exit_idx=[2,3],direction=[1,1],status=[1,0]))
    pf=SimpleNamespace(wrapper=SimpleNamespace(columns=[]),trades=SimpleNamespace(records=records))
    monkeypatch.setattr(simulator,'run_backtest',lambda **kw:pf)
    rows=proposal_records('SPY',bars,{'strategies':{'ma':{'params':{}}}},'2026-09-01','2026-09-01')
    assert [r['proposal_ordinal'] for r in rows]==[0,1]
    assert rows[0]['exit_ts']==index[2] and rows[1]['exit_ts'] is None
    assert rows[0]['bars_since_signal']==1 and rows[1]['bars_since_signal']==0
    first,second=[dict(r,dte=5) for r in rows]
    assert candidate_key(first)==original_key(first)
    assert candidate_key(first)!=candidate_key(second)


def test_batch_binds_duplicate_strategies_without_relying_on_merge_order(tmp_path):
    rows=[dict(symbol='SPY',strategy='ma',entry_ts=pd.Timestamp('2026-09-01'),proposal_ordinal=i,
               bars_since_signal=9 if i==0 else 0) for i in range(2)]
    def candidates(fresh,market,output):
        assert len(fresh)==1
        p=fresh[0]
        return pd.DataFrame([dict(symbol=p['symbol'],strategy=p['strategy'],entry_ts=p['entry_ts'],
            dte=d,bars_since_signal=p['bars_since_signal']) for d in [5,1]]),{}
    batch,_=candidate_batch(SimpleNamespace(candidates=candidates),rows,None,tmp_path)
    assert len({candidate_key(r) for r in batch.to_dict('records')})==4
    assert batch.groupby('proposal_ordinal').bars_since_signal.first().to_dict()=={0:9,1:0}


def response(status,body=None):
    return SimpleNamespace(status_code=status,json=lambda:body,close=lambda:None)


def test_tick_retry_preserves_pagination_and_validation():
    from options.data.massive_ticks import verify_capture
    pages=iter([response(502),response(200,{'status':'OK','results':[{'sip_timestamp':1}],
        'next_url':'https://api.massive.com/v3/quotes/O:SPY260918C00650000?cursor=next'}),
        requests.ConnectionError('secret URL must never leak'),response(200,{'status':'OK','results':[{'sip_timestamp':2}]})])
    calls=[]
    class Session:
        def get(self,url,**kwargs):
            calls.append(url);value=next(pages)
            if isinstance(value,Exception):raise value
            return value
    ticks=RetryingTicks(api_key='test',session=Session())
    ticks.session.sleep=lambda _:None
    rows,manifest=ticks.capture('SPY260918C00650000','quotes',0,3)
    assert [r['sip_timestamp'] for r in rows]==[1,2]
    assert calls[0]==calls[1] and calls[2]==calls[3]
    assert len(manifest['transient_retries'])==2
    verify_capture(rows,manifest,contract='SPY260918C00650000',kind='quotes',start_ns=0,end_ns=3)


def test_tick_retry_is_bounded_and_does_not_retry_permanent_errors():
    for code,expected in [(502,5),(401,1),(403,1),(404,1)]:
        calls=[]
        session=RetrySession(SimpleNamespace(get=lambda *a,**k:(calls.append(1) or response(code))),sleep=lambda _:None)
        assert session.get('endpoint').status_code==code
        assert len(calls)==expected
    session=RetrySession(SimpleNamespace(get=lambda *a,**k:response(502)),sleep=lambda _:None,clock=lambda:1,deadline=1.5)
    with pytest.raises(TimeoutError):session.get('endpoint')


def test_parent_reuse_binds_actual_scope_without_relabeling(tmp_path):
    parent=tmp_path/'parent';entry=parent/'features/SPY/entry';entry.mkdir(parents=True)
    (entry/'features.parquet').write_bytes(b'retained feature bytes')
    declaration=dict(contract='old',symbol='SPY',proposals=[dict(strategy='ma')])
    seal(entry,declaration,['features.parquet']);before=sha(entry/'complete.json')
    manifest=tmp_path/'parent.json'
    manifest.write_text(json.dumps(dict(root=str(parent),contract_identity='old',
        anchors={'features/SPY/entry/complete.json':before})))
    inherited=ParentArtifacts({'inherited_artifacts':{'path':str(manifest),'sha256':sha(manifest)}})
    assert inherited.resolve('features/SPY/entry',dict(declaration,contract='new',proposals=[dict(strategy='ma',proposal_ordinal=0)]))==entry
    assert sha(entry/'complete.json')==before
    with pytest.raises(ValueError,match='inputs differ'):
        inherited.resolve('features/SPY/entry',dict(declaration,symbol='AAPL'))
    (entry/'features.parquet').write_bytes(b'changed')
    with pytest.raises(ValueError,match='payload changed'):inherited.resolve('features/SPY/entry')


def test_training_join_keeps_both_collision_outcomes(tmp_path):
    from incubator.recovery_v6.training import assemble_delta
    features=tmp_path/'features';features.mkdir()
    rows=[dict(symbol='SPY',strategy='ma',dte=5,entry_ts=pd.Timestamp('2026-09-01'),
               proposal_ordinal=i,x=float(i)) for i in [0,1]]
    pd.DataFrame(rows).to_parquet(features/'features.parquet',index=False)
    seal(features,dict(contract='test'),['features.parquet'])
    candidates=[]
    for i,row in enumerate(rows):
        key=candidate_key(row);label=tmp_path/'labels'/str(i);label.mkdir(parents=True)
        (label/'label.json').write_text(json.dumps(dict(exit_ts='2026-09-02',fill_exit_ts='2026-09-02',
             net_return=.1 if i==0 else -.2,label_excess=1-i)))
        seal(label,dict(feature_sha256=sha(features/'complete.json')),['label.json'])
        candidates.append(dict(candidate_id=key,status='matured',feature_root=str(features),label_root=str(label)))
    symbol=tmp_path/'run/symbols/SPY';symbol.mkdir(parents=True)
    (symbol/'inventory.json').write_text(json.dumps(dict(candidates=candidates)))
    seal(symbol,dict(contract='test'),['inventory.json'])
    delta=assemble_delta(tmp_path/'run',['x'])
    assert len(delta)==2 and delta.candidate_id.nunique()==2
    assert delta.set_index('x').net_return.to_dict()=={0.:.1,1.:-.2}
