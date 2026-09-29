from copy import deepcopy

from nn_meta.v7.execution_cohorts import cohorts,cover_horizons,members_for_bucket
from nn_meta.v7.execution_jobs import compact_key,proposal_from_key
from nn_meta.v7.execution_frontier_v2 import discover_execution
from nn_meta.v7.replay_clocks import ReplayClocks
from tests.test_v7_execution_frontier import case


def test_every_horizon_matches_independent_replay_without_materializing_aliases(tmp_path):
    p,clocks,e,c=case(tmp_path)
    rows=[(*compact_key(dict(symbol=p['symbol'],decision_ns=p['decision_ns'],exit_decision_ns=ending,
            censored_ns=clocks[-1] if ending is None else None,is_put=False,exit_stock_ticker='')),i+1)
          for i,ending in enumerate([clocks[1],clocks[2],clocks[4],clocks[7],None])]
    def run(proposal,target):
        found=discover_execution(proposal,ReplayClocks(clocks),e.archive,e.references,e.sessions,select_contract=lambda t:c)
        return dict(found,status=found['replay']['status'],label_complete=found['replay']['label_complete'])
    buckets=list(cover_horizons(rows,'sid',1,run))
    assert len(buckets)<len(rows)
    seen=set()
    for bucket in buckets:
        for row in members_for_bucket(bucket,rows,'sid',seen):
            proposal=proposal_from_key(row[:6],'sid')
            expected=run(proposal,1)
            represented=deepcopy(bucket['result'])
            represented['proposal_id']=proposal['proposal_id']
            represented['replay']['proposal_id']=proposal['proposal_id']
            assert represented==expected
            seen.add(tuple(row[:6]))
    assert len(seen)==len(rows)
    assert sum(b['proposal_weight'] for b in buckets)==sum(r[6] for r in rows)


def test_cohorts_keep_direction_and_entry_distinct():
    rows=[('A',1,3,-1,0,'',1),('A',1,4,-1,1,'',1),('A',2,4,-1,0,'',1)]
    assert [key for key,group in cohorts(rows)]==[('A',1,0),('A',1,1),('A',2,0)]
