import sqlite3
from types import SimpleNamespace
import pytest
import pandas as pd
from scripts.plan_v7_frontier_lookahead import plan


def test_prefetch_stays_in_session_subtracts_coverage_and_is_bounded():
    minute=60*10**9;start=pd.Timestamp('2022-03-15T19:56Z').value
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ranges(contract,kind,start_ns,end_ns)')
    db.execute('INSERT INTO ranges VALUES (?,?,?,?)',('SPY220318C00420000','quotes',start+minute,start+2*minute))
    request=dict(provider='massive',kind='quotes',contract='SPY220318C00420000',start_ns=start,end_ns=start+30*10**9+1,request_id='actual')
    cases=[dict(pending=[request])];archive=SimpleNamespace(db=db)
    hours=SimpleNamespace(at=lambda s,d:dict(open_ns=start-300*minute,close_ns=start+4*minute))
    found,expanded=plan(cases,archive,hours,10)
    assert [(r['start_ns'],r['end_ns']) for r in found]==[(start,start+minute),(start+2*minute,start+4*minute)]
    assert expanded[0]['required_end_ns']==request['end_ns']
    assert expanded[0]['prefetch_end_ns']==start+4*minute
    with pytest.raises(ValueError,match='One to ten'):plan(cases,archive,hours,11)
    request['end_ns']=start+5*minute
    with pytest.raises(ValueError,match='outside'):plan(cases,archive,hours,10)
