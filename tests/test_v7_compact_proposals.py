import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from nn_meta.v7.entry_eligibility import EntryEligibility
from nn_meta.v7.compact_proposals import SCHEMA, write_proposals, read_proposals
from nn_meta.v7.proposal_store import build_features, build_proposals, StoredFeatures, StoredProposals
from nn_meta.v7.proposals import causal_proposal_batches
from nn_meta.v7.storage import sha
from tests.test_v7_proposal_store import chart_fixture


def eligible_fixture(tmp_path):
    chart, variants=chart_fixture()
    sessions=pd.DataFrame([dict(date='2022-03-15',security_id='fixture',stock_ticker='OLD',
                                membership_available_at='2022-03-15T13:45Z')])
    source=tmp_path/'membership.json';source.write_text(sessions.to_json(orient='records'))
    inputs={str(source):sha(source)}
    entry=EntryEligibility(sessions,chart.calendar,security_id='fixture',sources=inputs)
    build_features(tmp_path/'features',chart,variants,inputs=inputs,reserve_bytes=0)
    store=StoredFeatures(tmp_path/'features')
    return chart,variants,store,entry


def test_entry_membership_filters_only_known_entries_and_preserves_exits(tmp_path):
    chart,variants,store,entry=eligible_fixture(tmp_path)
    routing={'2022-03-15':'OLD','2022-03-16':'NEW'}
    report=build_proposals(tmp_path/'proposals',store,symbol='fixture',start='2022-03-15',end='2022-03-16',
        symbols_by_date=routing,eligibility=entry,reserve_bytes=0,row_batch_size=3)
    rows=list(StoredProposals(tmp_path/'proposals',features=store).rows(batch_size=2))
    all_rows=[r for _,batch in causal_proposal_batches('fixture',chart,variants,start='2022-03-15',end='2022-03-16') for r in batch]
    expected=[r for r in all_rows if entry.admits(r['decision_ns'],routing[r['decision_at'].strftime('%Y-%m-%d')])]
    assert report['entry_filter_applied'] and report['generated']==len(all_rows)
    assert report['proposals']==len(expected)==len(rows)>0
    assert report['excluded_not_member']==len(all_rows)-len(expected)>0
    assert report['variants']==len(variants)
    assert not list((tmp_path/'proposals').rglob('*.jsonl'))
    expected_by_key={(r['variant_id'],r['decision_ns'],r['right']):r for r in expected}
    for row in rows:
        original=expected_by_key[row['variant_id'],row['decision_ns'],row['right']]
        assert row['symbol']=='OLD' and row['decision_ns']>=pd.Timestamp('2022-03-15T13:45Z').value
        assert row['bars_since_previous_signal']==original['bars_since_previous_signal']
        assert row['exit_decision_ns']==(original['exit_decision_at'].value if original['proposal_closed'] else None)
    assert any(r['exit_stock_ticker']=='NEW' for r in rows if r['proposal_closed'])
    for p in (tmp_path/'proposals').glob('batches/*/proposals.parquet'):
        file=pq.ParquetFile(p)
        assert file.schema_arrow.equals(SCHEMA)
        assert all(file.metadata.row_group(i).num_rows<=3 for i in range(file.num_row_groups))


def test_empty_entry_universe_keeps_complete_variant_inventory(tmp_path):
    chart,variants,store,entry=eligible_fixture(tmp_path)
    empty=pd.DataFrame(columns=['date','security_id','stock_ticker','membership_available_at'])
    none=EntryEligibility(empty,chart.calendar,security_id='fixture',sources=entry.binding['sources'])
    report=build_proposals(tmp_path/'none',store,symbol='fixture',start='2022-03-15',end='2022-03-16',
        eligibility=none,reserve_bytes=0)
    assert report['proposals']==report['censored']==0 and report['variants']==20
    assert report['generated']==report['excluded_not_member']>0
    assert list(StoredProposals(tmp_path/'none').rows())==[]


def test_membership_mapping_and_snapshot_changes_cannot_resume_old_output(tmp_path):
    chart,variants,store,entry=eligible_fixture(tmp_path)
    with pytest.raises(ValueError,match='dated membership'):
        entry.admits(pd.Timestamp('2022-03-15T14:00Z').value,'WRONG')
    with pytest.raises(ValueError,match='membership sources'):
        entry.binding['sources']={'unbound':'source'}
        build_proposals(tmp_path/'bad',store,symbol='fixture',start='2022-03-15',end='2022-03-16',eligibility=entry,reserve_bytes=0)


def test_partial_compact_write_is_preserved_and_resume_reuses_completed_batches(tmp_path,monkeypatch):
    from nn_meta.v7 import compact_proposals
    chart,variants,store,entry=eligible_fixture(tmp_path)
    original=compact_proposals.write_proposals
    calls=[]
    def interrupted(*a,**kw):
        calls.append(1)
        if len(calls)==2:raise RuntimeError('Interrupted compact write')
        return original(*a,**kw)
    monkeypatch.setattr(compact_proposals,'write_proposals',interrupted)
    path=tmp_path/'proposals'
    kwargs=dict(symbol='fixture',start='2022-03-15',end='2022-03-16',reserve_bytes=0,batch_columns=4)
    with pytest.raises(RuntimeError,match='Interrupted'):build_proposals(path,store,**kwargs)
    first=path/'batches/0/complete.json';digest=sha(first)
    assert not (path/'summary').exists() and len(list((path/'batches').glob('1.partial-*')))==1
    build_proposals(path,store,**kwargs)
    assert sha(first)==digest and len(calls)==6
    assert StoredProposals(path).report['variants']==len(variants)
    (path/'batches/0/proposals.parquet').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='integrity'):StoredProposals(path)


@pytest.mark.parametrize('change',['extra_field','signal_gap_overflow','wrong_id','wrong_clock'])
def test_compaction_refuses_silent_information_loss(tmp_path,change):
    from nn_meta.multitimeframe_catalog import registered_catalog
    from nn_meta.v7.storage import identity
    variant=registered_catalog(['TEST'])['records'][0]
    decision=pd.Timestamp('2022-03-15T14:00Z')
    key=dict(symbol='TEST',variant_id=variant['variant_id'],decision_ns=decision.value,right='C')
    row=dict(proposal_id=identity(dict(schema='v7-proposal-v1',**key)),**key,
        decision_at=decision,exit_decision_at=pd.NaT,censored_at=decision+pd.Timedelta(minutes=30),
        proposal_closed=False,signal_minutes=variant['signal_minutes'],strategy=variant['strategy'],
        params=variant['params'],bars_since_previous_signal=1,simulator_policy={'policy':'fixture'})
    declaration=dict(variants=[variant],symbols_by_date=None,simulator_policy={'policy':'fixture'})
    if change=='extra_field':row['new_training_field']=3
    if change=='signal_gap_overflow':row['bars_since_previous_signal']=2**32
    if change=='wrong_id':row['proposal_id']='different'
    if change=='wrong_clock':row['decision_ns']+=1
    with pytest.raises(ValueError):write_proposals(tmp_path/'bad.parquet',[row],declaration)
