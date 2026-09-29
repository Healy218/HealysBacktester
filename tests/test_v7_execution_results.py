import sqlite3

import pytest

from nn_meta.v7.execution_results import initialize,store_result,load_result


def test_payload_sharing_reconstructs_each_original_path_and_rolls_back_atomically():
    db=sqlite3.connect(':memory:');initialize(db)
    request={'request_id':'request','contract':'AAPL260918C00200000','start_ns':1,'end_ns':2}
    def result(pid,selection):
        return dict(path_id=pid,proposal_id=pid,selection_id=selection,status='capture_incomplete',label_complete=False,
                    pending=[request],replay={'proposal_id':pid,'fills':[{'quantity':1}]},shared_result_id='shared')
    proposals=[dict(proposal_id='p1',security_id='sid',exit_decision_ns=300),
               dict(proposal_id='p2',security_id='sid',exit_decision_ns=400)]
    with db:
        for i,p in enumerate(proposals):store_result(db,result(p['proposal_id'],'s'+str(i)),p,i+1,10+i)
    assert db.execute('SELECT COUNT(*) FROM contents').fetchone()==(1,)
    assert db.execute('SELECT COUNT(*) FROM pending').fetchone()==(1,)
    for i,p in enumerate(proposals):
        restored=load_result(db,p['proposal_id'])
        assert restored['replay']['proposal_id']==p['proposal_id']
        assert restored['source_horizon']==p and restored['selection_id']=='s'+str(i)
        assert restored['source_multiplicity']==10+i and restored['target_dte']==i+1
    with pytest.raises(RuntimeError):
        with db:
            store_result(db,result('p3','s3'),dict(proposals[0],proposal_id='p3'),5,100)
            raise RuntimeError('interrupted')
    assert db.execute('SELECT COUNT(*) FROM paths').fetchone()==(2,)
    assert db.execute('SELECT COUNT(*) FROM links').fetchone()==(2,)
