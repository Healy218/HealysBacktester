from __future__ import annotations
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from incubator.continual.storage import seal,verify,sha
from incubator.continual.training import prepare_arrays,split_metadata,train_member,evaluate


def test_sealed_payload_and_declaration_cannot_be_reused_after_change(tmp_path):
    (tmp_path/'data').write_text('original')
    seal(tmp_path,{'cutoff':'2026-09-25'},['data'])
    verify(tmp_path,{'cutoff':'2026-09-25'})
    with pytest.raises(ValueError,match='inputs changed'):verify(tmp_path,{'cutoff':'2026-09-28'})
    (tmp_path/'data').write_text('altered')
    with pytest.raises(ValueError,match='payload changed'):verify(tmp_path)


def test_purge_uses_actual_fill_end_and_never_admits_pending_labels():
    frame=pd.DataFrame(dict(entry_ts=pd.to_datetime(['2026-09-01']*4+['2026-09-10']),
        exit_ts=pd.to_datetime(['2026-09-02','2026-09-02','2026-09-09',None,'2026-09-11']),
        fill_exit_ts=pd.to_datetime(['2026-09-02','2026-09-10','2026-09-09',None,'2026-09-11']),
        label_excess=[1,1,1,np.nan,0],net_return=[.1,.1,.1,np.nan,-.1]))
    train,val=split_metadata(frame,pd.Timestamp('2026-09-10'),1)
    assert train.tolist()==[True,False,False,False,False]
    assert val.tolist()==[False,False,False,False,True]


def test_full_candidate_enumeration_retains_open_status_and_ignores_trade_selection(monkeypatch):
    from incubator.continual.data import proposal_records
    from nn_meta import proposals,config
    from portfolio import simulator
    index=pd.date_range('2026-09-01 13:30',periods=4,freq='15min')
    bars=pd.DataFrame({'Close':[100,101,102,103]},index=index)
    signals=pd.DataFrame(True,index=index,columns=['one'])
    monkeypatch.setattr(proposals,'single_signals',lambda *a:[signals,None,None,None])
    monkeypatch.setattr(config,'WINDOW_START','2026-09-01')
    records=pd.DataFrame(dict(entry_idx=[0,2],exit_idx=[1,3],direction=[0,0],status=[1,0]))
    pf=SimpleNamespace(wrapper=SimpleNamespace(columns=[]),trades=SimpleNamespace(records=records))
    monkeypatch.setattr(simulator,'run_backtest',lambda **kw:pf)
    rows=proposal_records('SPY',bars,{'strategies':{'ma':{'params':{}}}},'2026-09-01','2026-09-01')
    assert len(rows)==2 and rows[0]['closed'] and not rows[1]['closed']
    assert rows[1]['exit_ts'] is None
    assert rows[1]['bars_since_signal']==2


def small_data(tmp_path):
    days=pd.date_range('2026-08-01',periods=30,freq='D')
    def frame(selected):
        return pd.DataFrame({'entry_ts':selected,'exit_ts':selected+pd.Timedelta(hours=1),
            'fill_exit_ts':selected+pd.Timedelta(hours=1),
            'label_excess':[i%2 for i in range(len(selected))],
            'net_return':[.1 if i%2 else -.2 for i in range(len(selected))],
            'x':np.arange(len(selected),dtype=float),'z':np.ones(len(selected))})
    base=tmp_path/'base.parquet';delta=tmp_path/'delta.parquet'
    frame(days[:20]).to_parquet(base,index=False);frame(days[20:]).to_parquet(delta,index=False)
    return base,delta


def test_streamed_arrays_append_rows_purge_and_preserve_base(tmp_path):
    base,delta=small_data(tmp_path);digest=sha(base)
    root=tmp_path/'arrays'
    prepare_arrays(base,delta,root,['x','z'],5,1,'2026-08-21')
    doc=json.loads((root/'arrays.json').read_text())
    assert doc['sizes']=={'train':24,'validation':5}
    assert sha(base)==digest
    before=sha(root/'complete.json')
    prepare_arrays(base,delta,root,['x','z'],5,1,'2026-08-21')
    assert sha(root/'complete.json')==before
    with pytest.raises(ValueError,match='inputs changed'):
        prepare_arrays(base,delta,root,['z','x'],5,1,'2026-08-21')


def test_extension_cannot_duplicate_base_period(tmp_path):
    base,delta=small_data(tmp_path)
    with pytest.raises(ValueError,match='overlaps'):
        prepare_arrays(base,delta,tmp_path/'arrays',['x','z'],5,1,'2026-08-22')


def test_real_lightgbm_member_retrain_resume_and_parent_comparison(tmp_path):
    import lightgbm as lgb
    import joblib
    base,delta=small_data(tmp_path);arrays=tmp_path/'arrays'
    prepare_arrays(base,delta,arrays,['x','z'],5,1,'2026-08-21')
    parent=tmp_path/'parent'/'seed';parent.mkdir(parents=True)
    x=np.array([[i,i%3] for i in range(40)],dtype=float)
    common=dict(n_estimators=12,min_child_samples=2,num_leaves=3,verbosity=-1,n_jobs=1)
    joblib.dump(lgb.LGBMClassifier(**common).fit(x,np.arange(40)%2),parent/'model.joblib')
    joblib.dump(lgb.LGBMRegressor(**common).fit(x,np.arange(40)*.001),parent/'magnitude.joblib')
    digest=sha(parent/'model.joblib');dest=tmp_path/'candidate'/'seed'
    train_member(arrays,parent,dest,1)
    before=sha(dest/'complete.json');train_member(arrays,parent,dest,1)
    assert sha(dest/'complete.json')==before and sha(parent/'model.joblib')==digest
    result=evaluate(arrays,dest.parent,parent.parent,['seed'])
    assert result['status'] in {'passed','rejected'}
    assert not result['deployment_approved'] and result['validation_rows']==5
    assert np.isfinite(result['metrics']['candidate']['return_mse'])


def test_market_records_complete_empty_coverage_and_reuses_it(tmp_path,monkeypatch):
    from incubator.continual.market import ResearchMarket
    obj=ResearchMarket.__new__(ResearchMarket);obj.root=tmp_path;obj.evidence=[]
    called=[]
    def pages(path,params):called.append(path);return [],{'complete':True}
    obj.pages=pages
    assert obj.get_contract_bars('SPY260918C00650000','2026-09-01','2026-09-02','15m').empty
    assert obj.get_contract_bars('SPY260918C00650000','2026-09-01','2026-09-02','15m').empty
    assert len(called)==1
    with pytest.raises(ValueError,match='frozen'):obj.get_contract_bars('SPY260918C00650000','2026-09-01','2026-09-02','1d')


def test_partial_option_path_remains_pending_until_exit_bar_closes():
    from incubator.continual.data import terminal_label
    exit_ts=pd.Timestamp('2026-09-01 15:00')
    assert not terminal_label({'executed':True,'fill_exit_ts':'2026-09-01 14:45'},exit_ts)
    assert not terminal_label({'executed':True,'fill_exit_ts':'2026-09-01 15:00'},exit_ts)
    assert terminal_label({'executed':True,'fill_exit_ts':'2026-09-01 15:15'},exit_ts)
    assert terminal_label({'executed':False,'fill_exit_ts':None},exit_ts)


def test_rejected_or_older_freezes_cannot_replace_accepted_pointer(tmp_path):
    from incubator.continual.storage import publish_candidate
    def candidate(name):
        p=tmp_path/name;p.mkdir();(p/'model').write_text(name);seal(p,{'name':name},['model']);return p
    accepted=candidate('accepted');rejected=candidate('rejected');old=candidate('old')
    publish_candidate(tmp_path,accepted,'2026-09-25','passed')
    original=(tmp_path/'latest-accepted.json').read_bytes()
    publish_candidate(tmp_path,rejected,'2026-09-28','rejected')
    assert (tmp_path/'latest-accepted.json').read_bytes()==original
    publish_candidate(tmp_path,old,'2026-09-24','passed')
    assert (tmp_path/'latest-accepted.json').read_bytes()==original
    assert json.loads((tmp_path/'latest-candidate.json').read_text())['path']==str(rejected)
