import json
from pathlib import Path
import pytest
from scripts.activate_v6_midpoint import amendment, sha, CHANGED, ADDED, POLICY


def setup(tmp_path,monkeypatch):
    runtime={}
    for name in (*CHANGED,'signals/stable.py'):
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('old')
        runtime[name]=sha(path)
    for name in (*CHANGED,*ADDED):
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('new')
    previous=tmp_path/'previous.json'
    previous.write_text(json.dumps(dict(status='passed',schema='v6-forward-activation-v1',
                                       runtime_sha256=runtime,evidence_sha256={})))
    report=tmp_path/'report.json'
    report.write_text(json.dumps(dict(status='passed',pricing_policy=POLICY,
        candidate_sources={n:sha(tmp_path/n) for n in (*CHANGED,*ADDED)},inputs={},
        closed_records_unchanged=True,realized_equity_unchanged=True,idempotent=True,same_quote_cost_only=True)))
    tests=tmp_path/'tests.xml'
    tests.write_text('<testsuites><testsuite tests="180"><testcase classname="tests.test_v6_midpoint_pricing"/><testcase classname="tests.test_v6_midpoint_pricing"/></testsuite></testsuites>')
    monkeypatch.setattr('scripts.activate_v6_midpoint.subprocess.check_output',lambda *a,**k:'commit\n')
    return previous,report,tests


def test_amendment_preserves_unchanged_dependencies_and_binds_price_evidence(tmp_path,monkeypatch):
    previous,report,tests=setup(tmp_path,monkeypatch)
    result=amendment(tmp_path,previous,report,tests)
    assert result['pricing_policy']==POLICY and result['tests']==180
    assert result['pricing_amendment']['previous_activation_sha256']==sha(previous)
    assert result['runtime_sha256']['signals/stable.py']==sha(tmp_path/'signals/stable.py')
    assert result['evidence_sha256'][str(report)]==sha(report)


@pytest.mark.parametrize('change',['feature','test_failure','missing_mid_tests','ledger_evidence'])
def test_amendment_rejects_unrelated_changes_or_incomplete_evidence(tmp_path,monkeypatch,change):
    previous,report,tests=setup(tmp_path,monkeypatch)
    if change=='feature':(tmp_path/'signals/stable.py').write_text('different feature')
    elif change=='test_failure':tests.write_text(tests.read_text().replace('tests="180"','tests="180" failures="1"'))
    elif change=='missing_mid_tests':tests.write_text(tests.read_text().replace('test_v6_midpoint_pricing','other'))
    else:
        doc=json.loads(report.read_text());doc['closed_records_unchanged']=False;report.write_text(json.dumps(doc))
    with pytest.raises(ValueError):amendment(tmp_path,previous,report,tests)
