import json
from dataclasses import asdict
import pytest
from scripts.activate_v6_option_risk import amendment, CHANGED, ADDED, POLICY, RISK, CHECKS, sha
from options.paper_risk import V6_OPTION_RISK
from options.paper_pricing import MIDPOINT_POLICY


def fixture(tmp_path,monkeypatch):
    from scripts import activate_v6_option_risk as module
    monkeypatch.setattr(module.subprocess,'check_output',lambda *a,**k:'test-commit\n')
    prior_sources={}
    for name in (*CHANGED,'frozen_model.py'):
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('old')
        prior_sources[name]=sha(p)
        if name in CHANGED:p.write_text('new')
    for name in ADDED:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('added')
    previous=tmp_path/'previous.json'
    previous.write_text(json.dumps(dict(schema='v6-forward-activation-v1',status='passed',
        pricing_policy='option-midpoint-paper-v1',runtime_sha256=prior_sources,evidence_sha256={})))
    data=tmp_path/'ledger-evidence.json';data.write_text('{}')
    report=tmp_path/'report.json'
    report.write_text(json.dumps(dict(status='passed',pricing_policy=POLICY,option_risk_policy=RISK,
        previous_activation_sha256=sha(previous),candidate_sources={n:sha(tmp_path/n) for n in (*CHANGED,*ADDED)},
        inputs={str(data):sha(data)},**dict.fromkeys(CHECKS,True))))
    tests=tmp_path/'tests.xml'
    cases=''.join(f'<testcase classname="{name}"/>' for name,count in
        [('test_v6_option_risk',10),('test_option_paper_risk',8),('test_v6_midpoint_pricing',2)] for _ in range(count))
    tests.write_text(f'<testsuites><testsuite tests="1600" failures="0" errors="0" skipped="0">{cases}</testsuite></testsuites>')
    return previous,report,tests


@pytest.mark.parametrize('mutation',['none','source','evidence','open_book','wrong_policy','tests'])
def test_guarded_amendment_rejects_unreviewed_state_or_code(tmp_path,monkeypatch,mutation):
    previous,report,tests=fixture(tmp_path,monkeypatch)
    if mutation=='source':(tmp_path/'frozen_model.py').write_text('changed')
    if mutation=='evidence':(tmp_path/'ledger-evidence.json').write_text('changed')
    if mutation in ('open_book','wrong_policy'):
        doc=json.loads(report.read_text())
        if mutation=='open_book':doc['empty_open_book']=False
        else:doc['option_risk_policy']={**RISK,'premium_stop_fraction':.05}
        report.write_text(json.dumps(doc))
    if mutation=='tests':tests.write_text('<testsuites><testsuite tests="1600" failures="1"/></testsuites>')
    if mutation!='none':
        with pytest.raises(ValueError):amendment(tmp_path,previous,report,tests)
    else:
        result=amendment(tmp_path,previous,report,tests)
        assert result['option_risk_policy']==asdict(V6_OPTION_RISK)==RISK
        assert result['pricing_policy']==MIDPOINT_POLICY==POLICY
        assert result['runtime_sha256']['frozen_model.py']==sha(tmp_path/'frozen_model.py')
