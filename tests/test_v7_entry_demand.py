from datetime import date
import json

import pandas as pd
import pytest

from nn_meta.v7.entry_demand import build_entry_demand,EntryDemand,TARGETS
from nn_meta.v7.proposal_store import build_proposals,StoredProposals
from nn_meta.v7.storage import sha,receipt,verify
from nn_meta.v7.quotes import capture_union
from tests.test_v7_compact_proposals import eligible_fixture


def fixture(tmp_path,*,empty=False):
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    _,_,features,eligibility=eligible_fixture(tmp_path)
    if empty:
        from nn_meta.v7.entry_eligibility import EntryEligibility
        eligibility=EntryEligibility(pd.DataFrame(columns=['date','security_id','stock_ticker','membership_available_at']),
            features.declaration['calendar'],security_id='fixture',sources=eligibility.binding['sources'])
    path=tmp_path/'proposals'
    build_proposals(path,features,symbol='fixture',start='2022-03-15',end='2022-03-16',
        symbols_by_date={'2022-03-15':'OLD','2022-03-16':'NEW'},eligibility=eligibility,reserve_bytes=0)
    store=StoredProposals(path,features=features)
    chain=tmp_path/'chain';chain.mkdir()
    # A put first seen today cannot be selected. All five targets choose the
    # same previously observed call; their separate row identities must survive.
    pd.DataFrame([dict(root='OLD',ticker='O:OLD220318'+right+'00100000',
        expiry=date(2022,3,18),right=right,strike=100.,first_seen=seen) for right,seen in
        [('C',date(2022,3,14)),('P',date(2022,3,15))]]).to_parquet(chain/'contracts.parquet',index=False)
    receipt(chain,dict(identity='fixture'))
    return store,chain


def test_actual_proposal_demand_reuses_selections_and_exact_causal_windows(tmp_path,monkeypatch):
    store,chain=fixture(tmp_path)
    kwargs=dict(reserve_bytes=0,expected_timeframes=(1,))
    path=tmp_path/'demand'
    report=build_entry_demand(path,[store],chain,**kwargs)
    demand=EntryDemand(path)
    proposals=list(store.rows())
    assert report['proposals']==len(proposals)>report['distinct_selection_decisions']
    assert sum(report['selection_statuses'].values())==5*report['distinct_selection_decisions']
    assert report['selection_statuses']['no_contract']>0
    assert report['selection_statuses']['selected']>0
    requests={r['request_id']:r for batch in demand.request_batches() for r in batch}
    assert len(requests)==report['requests']
    with pytest.raises(ValueError,match='contract/day'):
        list(demand.request_batches(maximum=1))
    for proposal in proposals:
        results=[demand.lookup(proposal,target_dte=target) for target in TARGETS]
        assert len({r['selection_id'] for r in results})==5
        assert len({tuple(r['request_ids']) for r in results})==1
        for result in results:
            assert result['raw_available_ns']==proposal['decision_ns']
            if proposal['right']=='P':
                assert result['status']=='no_contract' and result['request_ids']==[]
            else:
                assert result['status']=='selected' and result['first_seen']=='2022-03-14'
                assert len(result['request_ids'])==2
                for rid in result['request_ids']:
                    r=requests[rid]
                    assert r['contract']=='OLD220318C00100000'
                    assert r['end_ns']==proposal['decision_ns']
                    assert r['start_ns']==proposal['decision_ns']-90_000_000_000
    export=tmp_path/'export'
    exported=demand.export_requests(export)
    assert sum(b['requests'] for b in exported['batches'])==len(requests)
    all_scopes=[]
    for batch in exported['batches']:
        rows=json.loads((export/batch['path']).read_text())
        union=capture_union(rows)
        assert set(union['request_captures'])=={r['request_id'] for r in rows}
        all_scopes.extend((r['contract'],r['start_ns']//86_400_000_000_000) for r in rows)
    assert len(all_scopes)==len(requests)
    verify(export)
    digest=sha(path/'complete.json')
    monkeypatch.setattr(store,'rows',lambda **kw:pytest.fail('Repeated proposal scan'))
    assert build_entry_demand(path,[store],chain,**kwargs)==report
    assert sha(path/'complete.json')==digest
    (chain/'contracts.parquet').write_bytes(b'changed')
    with pytest.raises(ValueError,match='inputs'):demand.verify_bindings()


def test_entry_demand_refuses_unfiltered_or_incomplete_timeframes(tmp_path):
    store,chain=fixture(tmp_path)
    with pytest.raises(ValueError,match='timeframe'):build_entry_demand(tmp_path/'bad',[store],chain,reserve_bytes=0)
    store.declaration['entry_eligibility']=None
    with pytest.raises(ValueError,match='eligibility'):
        build_entry_demand(tmp_path/'bad',[store],chain,reserve_bytes=0,expected_timeframes=(1,))


def test_empty_membership_preserves_variant_census_without_capture_requests(tmp_path):
    store,chain=fixture(tmp_path,empty=True)
    path=tmp_path/'demand'
    report=build_entry_demand(path,[store],chain,reserve_bytes=0,expected_timeframes=(1,))
    assert report['variants']==20 and report['proposals']==report['requests']==report['feature_links']==0
    demand=EntryDemand(path)
    assert list(demand.request_batches())==[]
    assert demand.export_requests(tmp_path/'export')['batches']==[]
