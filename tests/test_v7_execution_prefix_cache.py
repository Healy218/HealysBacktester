from copy import deepcopy
import sqlite3
import pytest

from nn_meta.v7.execution_frontier_v2 import discover_execution
from nn_meta.v7.execution_prefix_cache import SharedExecutionWorker,reusable
from nn_meta.v7.entry_demand import selection_id
from nn_meta.v7.replay_clocks import ReplayClocks
from tests.test_v7_execution_frontier import case
from nn_meta.v7.execution_prefix_cache_v2 import SharedExecutionWorker as FactorizedWorker


@pytest.mark.parametrize('wrapper',[SharedExecutionWorker,FactorizedWorker])
def test_shared_stop_matches_independent_horizons_and_targets(tmp_path,wrapper):
    proposal,clocks,engine,contract=case(tmp_path)
    class Worker:
        def __init__(self):
            self.db=sqlite3.connect(':memory:');self.calls=0;self.inputs={}
            self.db.execute('CREATE TABLE selections(selection_id,status,contract)')
            for target in [1,5]:
                key=selection_id(proposal['symbol'],proposal['decision_ns'],proposal['right'],target)
                self.db.execute('INSERT INTO selections VALUES(?,?,?)',(key,'selected',contract))
        def select(self,*args):return contract
        def run(self,p,target):
            self.calls+=1
            result=discover_execution(p,ReplayClocks(clocks),engine.archive,engine.references,engine.sessions,select_contract=lambda t:contract)
            return dict(result,status=result['replay']['status'],label_complete=result['replay']['label_complete'],
                        selection_id=selection_id(p['symbol'],p['decision_ns'],p['right'],target),contract=contract)
        def close(self):self.db.close()
    worker=Worker();cached=wrapper(worker)
    first={**proposal,'exit_decision_ns':clocks[6]}
    later={**proposal,'proposal_id':'later','exit_decision_ns':clocks[8]}
    assert cached.run(first,1)['label_complete']
    actual=cached.run(later,5)
    assert cached.hits==1 and worker.calls==1
    actual.pop('shared_result_id',None)
    assert actual==worker.run(later,5)
    earlier={**proposal,'proposal_id':'earlier','exit_decision_ns':clocks[2]}
    assert cached.run(earlier,1)==worker.run(earlier,1)
    assert cached.hits==1
    cached.close()


def test_roll_and_exit_dependent_paths_are_never_shared(tmp_path):
    p,clocks,e,c=case(tmp_path)
    result=discover_execution(p,ReplayClocks(clocks),e.archive,e.references,e.sessions,select_contract=lambda t:c)
    result['status']=result['replay']['status']
    assert reusable(result,p)
    rolled=deepcopy(result);rolled['replay']['rolls']=1
    assert not reusable(rolled,p)
    missing=deepcopy(result);missing['status']='capture_incomplete';missing['replay']['risk_exit']=None
    missing['pending']=[{'purpose':'exit_sale'}]
    assert not reusable(missing,p)
    missing['pending']=[{'purpose':'held_mark'}]
    assert reusable(missing,p)
    assert not reusable(missing,{**p,'exit_decision_ns':clocks[2]})
