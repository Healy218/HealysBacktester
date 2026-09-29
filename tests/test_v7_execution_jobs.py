import sqlite3

import pytest

from nn_meta.v7.execution_jobs import compact_key, proposal_from_key, connect_jobs, add_batch


def row(**changes):
    return dict(symbol='AAPL',decision_ns=100,exit_decision_ns=200,censored_ns=None,
                is_put=False,exit_stock_ticker='AAPL',**changes)


def test_factorization_preserves_multiplicity_and_atomic_resume(tmp_path):
    db=connect_jobs(tmp_path/'jobs.sqlite3')
    base=row()
    assert add_batch(db,'batch-a','hash-a',[base,base])==(2,True)
    assert add_batch(db,'batch-a','hash-a',[base,base])==(2,False)
    assert db.execute('SELECT multiplicity FROM jobs').fetchone()==(2,)
    changed={**base,'exit_decision_ns':300}
    add_batch(db,'batch-b','hash-b',[base,changed])
    assert db.execute('SELECT SUM(multiplicity),COUNT(*) FROM jobs').fetchone()==(4,2)
    with pytest.raises(ValueError,match='changed'):
        add_batch(db,'batch-a','different',[base])
    def broken():
        yield base
        raise RuntimeError('interrupted')
    with pytest.raises(RuntimeError):add_batch(db,'batch-c','hash-c',broken())
    assert db.execute('SELECT SUM(multiplicity) FROM jobs').fetchone()==(4,)
    assert not db.execute('SELECT 1 FROM batches WHERE path="batch-c"').fetchone()
    db.close()


def test_horizons_direction_and_lifecycle_never_merge():
    base=row()
    rows=[base,{**base,'exit_decision_ns':300},{**base,'is_put':True},
          {**base,'exit_stock_ticker':'NEW'},{**base,'exit_decision_ns':None,'censored_ns':200}]
    assert len({compact_key(r) for r in rows})==len(rows)
    decoded=[proposal_from_key(compact_key(r),'sid') for r in rows]
    assert len({r['proposal_id'] for r in decoded})==len(rows)
    assert decoded[0]['exit_decision_ns']==200
    assert decoded[-1]['exit_decision_ns'] is None and decoded[-1]['censored_ns']==200
    assert proposal_from_key(compact_key(base),'other')['proposal_id']!=decoded[0]['proposal_id']


@pytest.mark.parametrize('changes',[{'exit_decision_ns':None},{'exit_decision_ns':99},
                                  {'censored_ns':250},{'decision_ns':100.0},{'is_put':1}])
def test_invalid_horizons_fail_closed(changes):
    with pytest.raises(ValueError):compact_key({**row(),**changes})
