import json
import pandas as pd
import pytest
from nn_meta.v7.dated_hours import compile_hours,DatedHours,MINUTE,validate_rules
from nn_meta.v7.execution import CaptureUnavailable
from nn_meta.v7.storage import sha


def fixture(tmp_path):
    source=tmp_path/'source';source.write_text('fictional historical exchange facts')
    evidence={str(source):sha(source)}
    doc=dict(schema='v7-dated-option-hours-v2',timezone='America/New_York',start='2022-03-11',end='2022-03-19',
        scope_roots=['OLD','SPY'],methodology='fictional unit test',default_sources=evidence,
        opening_sources=evidence,early_close_sources=evidence,default_close_extension_minutes=0,
        early_close_extension='same_as_regular',exceptions={'SPY':[
            dict(start='2022-03-11',extension_minutes=0,sources=evidence,description='old close'),
            dict(start='2022-03-15',extension_minutes=15,sources=evidence,description='effective change')]})
    declaration=tmp_path/'rules.json';declaration.write_text(json.dumps(doc))
    calendar=tmp_path/'calendar.json';calendar.write_text(json.dumps(dict(coverage_start='2022-03-11',coverage_end='2022-03-20',
        sessions=[dict(date=d,open='09:30',close='13:00' if d=='2022-03-18' else '16:00') for d in
                  ('2022-03-11','2022-03-14','2022-03-15','2022-03-16','2022-03-17','2022-03-18')])))
    return declaration,calendar,source


def test_dated_boundary_dst_early_close_weekend_cutoff_and_scope(tmp_path):
    declaration,calendar,source=fixture(tmp_path)
    h=compile_hours(declaration,calendar,tmp_path/'hours')
    assert h.at('SPY','2022-03-14')['close_ns']==pd.Timestamp('2022-03-14T20:00Z').value
    assert h.at('SPY','2022-03-15')['close_ns']==pd.Timestamp('2022-03-15T20:15Z').value
    assert h.at('SPY','2022-03-11')['close_ns']==pd.Timestamp('2022-03-11T21:00Z').value
    assert h.at('OLD','2022-03-18')['close_ns']==pd.Timestamp('2022-03-18T17:00Z').value
    assert h.at('SPY','2022-03-18')['close_ns']==pd.Timestamp('2022-03-18T17:15Z').value
    assert h.cutoff('SPY220319C00100000')==pd.Timestamp('2022-03-18T17:00Z').value
    assert h.sessions.get(('SPY','2022-03-15'))==h.at('SPY','2022-03-15')
    for root,day in [('UNKNOWN','2022-03-15'),('SPY','2022-03-13'),('SPY','2022-03-20')]:
        with pytest.raises(CaptureUnavailable):h.at(root,day)
    with pytest.raises(CaptureUnavailable):h.cutoff('SPY220325C00100000')
    original=sha(tmp_path/'hours/complete.json');compile_hours(declaration,calendar,tmp_path/'hours')
    assert sha(tmp_path/'hours/complete.json')==original
    source.write_text('changed evidence')
    with pytest.raises(ValueError,match='source changed'):h.verify_bindings()
    with pytest.raises(ValueError):DatedHours(tmp_path/'hours')


def test_bad_source_scope_and_ambiguous_rules_rejected(tmp_path):
    declaration,calendar,source=fixture(tmp_path);doc=json.loads(declaration.read_text())
    doc['exceptions']['SPY'].append(dict(doc['exceptions']['SPY'][-1]))
    with pytest.raises(ValueError,match='Overlapping'):validate_rules(doc)
    doc=json.loads(declaration.read_text());doc['exceptions']['SPY'][0]['sources']={}
    with pytest.raises(ValueError):validate_rules(doc)
    doc=json.loads(declaration.read_text());doc['exceptions']['SPY'][0]['extension_minutes']=True
    with pytest.raises(ValueError):validate_rules(doc)
