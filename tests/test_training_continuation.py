import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from nn_meta import build_meta_dataset as b, config
from nn_meta.mark_stream import load_mark_stream, stable_trade_id
from nn_meta.stream_assembly import assemble_streaming
from nn_meta.temporal_validation import post_freeze_folds, assign_purged_splits
from scripts.continue_v6_training import read_parent_scope


def test_scope_stream_reader_preserves_metadata_and_hash(tmp_path):
    original={'campaign':'parent','inputs':{'files':[
        {'path':'cache/bars_15m/x.parquet','sha256':'ignored'},
        {'path':'cache/surface_daily.parquet','sha256':'surface'},
        {'path':'source/nn_meta/model.py','sha256':'model'},
        {'path':'universe/universe_pit/2026-01.json','sha256':'pit'}],
        'runtime':{'python':'version'},'sha256':'full'},'window':['start','end']}
    p=tmp_path/'scope.json';p.write_text(json.dumps(original,sort_keys=True,indent=2)+'\n')
    got,digest,count=read_parent_scope(p)
    assert digest==hashlib.sha256(p.read_bytes()).hexdigest()
    assert count==4
    original['inputs']['files']=original['inputs']['files'][1:]
    assert got==original


def test_post_freeze_folds_are_disjoint_and_purged():
    days=pd.Series(pd.bdate_range('2024-08-26','2026-08-24'))
    folds=post_freeze_folds(days,frozen_until='2025-12-19')
    assert len(folds)==3
    for i,w in enumerate(folds):
        assert w.val_start>pd.Timestamp('2025-12-19')
        if i: assert folds[i-1].test_end<w.test_start
        rows=pd.DataFrame({'entry_ts':[w.val_start-pd.Timedelta(days=1),w.val_start],
                           'exit_ts':[w.val_start,w.test_start]})
        split=assign_purged_splits(rows,train_start=w.train_start,val_start=w.val_start,
            test_start=w.test_start,test_end=w.test_end,embargo='1D')
        assert split.tolist()==['purged','purged']
    with pytest.raises(ValueError,match='20 observed'):
        post_freeze_folds(days,frozen_until='2026-08-01')


def assembly_fixture(tmp_path, monkeypatch):
    from tests.test_mark_stream import _rows,_marks_for
    rows=_rows(); rows['entry_date']=rows.entry_ts.dt.normalize()
    rows['executed']=True;rows['fill_lag_s']=900.;rows['und_period_return']=[.01,np.nan]
    rows['optional_number']=[1.,None]
    rows['net_return']=[.18,np.nan]
    marks=_marks_for(rows)
    rd=tmp_path/'rows';md=tmp_path/'marks';rd.mkdir();md.mkdir()
    spec={'symbols':{s:{} for s in rows.symbol}}
    monkeypatch.setattr(b,'load_spec',lambda:spec)
    for s,grp in rows.groupby('symbol'):
        rp=rd/f'{s}.parquet'
        # First sorted symbol has a null-only optional numeric column.
        if s=='QQQ': grp['optional_number']=None
        grp.to_parquet(rp,index=False)
        b._write_provenance(rp,b._provenance({},config.DTE_GRID))
        marks[marks.trade_id.isin(stable_trade_id(grp))].to_parquet(md/rp.name,index=False)
    surface=pd.DataFrame({'underlying':['SPY','QQQ','SPY','QQQ'],
        'date':pd.to_datetime(['2025-01-01','2025-01-01','2025-01-02','2025-01-02']),
        **{c:[.1,.2,.3,.4] for c in b._SURFACE_COLS}}).sort_values('date')
    beta=surface[['underlying','date']].assign(beta_60d=[1.,1.2,1.,1.3])
    monkeypatch.setattr(b,'load_surface_features',lambda:surface)
    monkeypatch.setattr(b,'rolling_beta_60d',lambda:beta)
    monkeypatch.setattr(config,'META_DATASET_PARQUET',tmp_path/'dataset.parquet')
    return rd,md,rows,marks,surface,beta


def test_stream_assembly_retains_values_prior_day_joins_and_marks(tmp_path,monkeypatch):
    rd,md,rows,marks,surface,beta=assembly_fixture(tmp_path,monkeypatch)
    result=assemble_streaming(rd,md)
    actual=pd.read_parquet(config.META_DATASET_PARQUET)
    from nn_meta.feature_contract import require_current_dataset
    require_current_dataset(actual,b.load_spec())
    expected=b.add_context_features(b.join_surface_asof(rows,surface),surface,beta=beta)
    expected['label']=[np.nan if pd.isna(v) else float(v>0) for v in expected.net_return]
    expected['label_excess']=[np.nan if pd.isna(v) or pd.isna(u) else float(v>u)
        for v,u in zip(expected.net_return,expected.und_period_return)]
    expected['split']=b.assign_split(expected.entry_date)
    actual.attrs={};expected.attrs={}
    assert_frame_equal(actual.sort_values('symbol').reset_index(drop=True),
        expected.sort_values('symbol').reset_index(drop=True),check_like=True)
    assert result['dataset_rows']==2 and result['mark_rows']==5
    restored=load_mark_stream(tmp_path/'dataset.marks.parquet',trade_ids=stable_trade_id(rows.iloc[:1]))
    assert len(restored)==3 and restored.mark_ts.max()==rows.fill_exit_ts.iloc[0]


def test_stream_assembly_refuses_missing_endpoint_and_does_not_publish(tmp_path,monkeypatch):
    rd,md,rows,marks,_,_=assembly_fixture(tmp_path,monkeypatch)
    p=md/'QQQ.parquet';bad=pd.read_parquet(p).iloc[:1];bad.to_parquet(p,index=False)
    with pytest.raises(ValueError,match='Incomplete marks'):
        assemble_streaming(rd,md)
    assert not config.META_DATASET_PARQUET.exists()


def test_vector_mark_endpoints_follow_identity_under_row_reordering():
    from tests.test_mark_stream import _rows,_marks_for
    rows=_rows();rows['executed']=True
    marks=_marks_for(rows)
    assert b._marks_cover(rows.iloc[::-1],marks)
    assert not b._marks_cover(rows,marks.iloc[1:])


def test_reuse_completed_outputs_requires_matching_lineage_and_hashes(tmp_path,monkeypatch):
    from scripts import continue_v6_training as c
    monkeypatch.setattr(c,'ROOT',tmp_path)
    oldbase=tmp_path/'nn_meta/campaigns/old/v6';newbase=tmp_path/'nn_meta/campaigns/new/v6'
    monkeypatch.setattr(config,'ARTIFACTS',newbase/'artifacts')
    records=newbase/'runs/continuation';records.mkdir(parents=True)
    scope={'campaign':'new','reuse_completed':'old','parent_scope_sha256':'parent',
        'runtime':{},'feature_contract_version':'contract',
        'sources':{'nn_meta/stream_assembly.py':'assembly','nn_meta/training_jobs.py':'new'},
        'inputs':{'nn_meta/campaigns/new/v6/artifacts/baseline_spec.json':'spec'}}
    old=dict(scope,sources=dict(scope['sources'],**{'nn_meta/training_jobs.py':'old'}),
             inputs={'nn_meta/campaigns/old/v6/artifacts/baseline_spec.json':'spec'})
    oldbase.mkdir(parents=True);c.write(oldbase/'continuation_scope.json',old)
    for stage,folder in [('assemble','artifacts'),('experiments','reports/objective-comparisons')]:
        path=oldbase/folder/'output';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(stage.encode())
        rp=oldbase/'runs/continuation'/f'{stage}.json';rp.parent.mkdir(parents=True,exist_ok=True)
        c.write(rp,{'returncode':0,'outputs':{str(path.relative_to(tmp_path)):c.sha(path)}})
    c.reuse_outputs(scope,records)
    assert (newbase/'artifacts/output').read_bytes()==b'assemble'
    assert json.loads((records/'assemble.json').read_text())['reused_from']=='old'
    scope['sources']['nn_meta/stream_assembly.py']='different'
    with pytest.raises(ValueError,match='source changed'):
        c.reuse_outputs(scope,records)
