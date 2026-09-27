import json
import sqlite3
from tests.test_v7_entry_demand import fixture
from nn_meta.v7.entry_demand import build_entry_demand
from tests.test_v7_contract_blackouts import policy_at
from tests.test_v7_dated_hours import fixture as hours_fixture
from nn_meta.v7.dated_hours import compile_hours
from nn_meta.v7.storage import sha
from scripts.plan_v7_execution_envelopes import work


def test_envelopes_union_overlap_preserve_blackout_crossing_and_resume(tmp_path):
    (tmp_path/'data').mkdir()
    store,chain=fixture(tmp_path/'data')
    source=(tmp_path/'data'/'demand').resolve()
    build_entry_demand(source,[store],chain,reserve_bytes=0,expected_timeframes=(5,))
    policy=policy_at(tmp_path/'blackouts',day='2022-03-16')
    base=tmp_path/'hours-inputs';base.mkdir()
    declaration,calendar,_=hours_fixture(base)
    hours=compile_hours(declaration,calendar,tmp_path/'hours')
    output=tmp_path/'envelopes'
    args=('fixture',str(source),sha(source/'complete.json'),str(hours.path),str(policy.path),str(output))
    _,report=work(args)
    assert report['contracts']==1 and report['contract_days']==2  # Fixture scope ends March 16.
    assert report['additional_quote_ns']>0
    assert report['envelope_quote_ns']==report['existing_quote_ns']+report['additional_quote_ns']
    assert report['potential_blackout_crossings']==[dict(contract='OLD220318C00100000',date='2022-03-16',first_selected_date='2022-03-15')]
    with sqlite3.connect(output/'envelopes.sqlite3') as db:
        rows=db.execute('SELECT * FROM windows ORDER BY date').fetchall()
    assert rows[0][-1]==0 and rows[1][-1]==1
    digest=sha(output/'complete.json');assert work(args)[1]==report
    assert sha(output/'complete.json')==digest
    assert not report['realized_paths'] and not report['full_execution_coverage']
