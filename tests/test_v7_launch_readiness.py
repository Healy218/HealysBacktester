import json
from pathlib import Path

import pandas as pd
import pytest

from nn_meta.v7 import readiness
from nn_meta.v7.scope import declaration
from nn_meta.v7.storage import sha, receipt, identity


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(readiness, 'source_manifest', lambda root: {'producer.py':'code-hash'})
    monkeypatch.setattr(readiness, 'runtime_manifest', lambda: {'python':'test-runtime'})
    source = tmp_path/'inputs'
    write(source/'scope.json', declaration())
    write(source/'report.json', {'scope':declaration()})
    write(tmp_path/'verification.json', {'forbidden_rows':0})
    write(tmp_path/'chain/complete.json', {'complete':True})
    write(tmp_path/'evaluation.json', {'evaluation':{}})
    universe = tmp_path/'universe'
    universe.mkdir()
    pd.DataFrame([dict(month='2022-02',ticker='SPY',security_id='spy-id')]).to_parquet(universe/'membership.parquet')
    write(universe/'report.json', dict(identity_boundaries_verified=True, historical_symbols=1,
        historical_securities=1,rows=1,lookback_policy=dict(excluded_sessions=[
            '2022-03-08','2022-03-09','2022-03-10','2022-03-11','2022-03-14'])))
    write(universe/'provenance.json', {'code':{}})
    receipt(universe, {'identity':'test-universe'})
    coverage = tmp_path/'coverage'
    write(coverage/'report.json', dict(eligible_sessions=1,resolved_alias_sessions=0,remaining_zero_sessions=0,
        sources={'universe/complete.json':sha(universe/'complete.json')}))
    receipt(coverage, {'identity':'test-coverage'})
    from nn_meta.multitimeframe_catalog import registered_catalog
    plan = dict(catalog=registered_catalog(['SPY']), membership_receipt_sha256=sha(universe/'complete.json'))
    plan['plan_sha256'] = identity(plan)
    write(tmp_path/'plan.json', {'plan':plan})
    active = dict(history_start='2022-03-15',history_end='2026-09-14',working_inputs='inputs',
        input_report_sha256=sha(source/'report.json'), verification='verification.json',
        verification_sha256=sha(tmp_path/'verification.json'),chain='chain',
        chain_receipt_sha256=sha(tmp_path/'chain/complete.json'),evaluation='evaluation.json',
        evaluation_file_sha256=sha(tmp_path/'evaluation.json'),universe='universe',
        universe_receipt_sha256=sha(universe/'complete.json'),coverage_inventory='coverage',
        coverage_receipt_sha256=sha(coverage/'complete.json'),readiness_evidence={})
    active.update(plan='plan.json', plan_file_sha256=sha(tmp_path/'plan.json'), plan_sha256=plan['plan_sha256'])
    from dataclasses import asdict
    from nn_meta.v7.execution import QuotePolicy
    from options.paper_risk import V7_OPTION_RISK
    write(tmp_path/'pricing.json', {'quote_policy':asdict(QuotePolicy()),
                                  'option_risk_policy':asdict(V7_OPTION_RISK)})
    active.update(option_paper_pricing='pricing.json', option_paper_pricing_sha256=sha(tmp_path/'pricing.json'))
    return active


def test_plan_cannot_reintroduce_excluded_or_missing_historical_symbols(tmp_path, monkeypatch):
    active = fixture(tmp_path, monkeypatch)
    plan = json.loads((tmp_path/'plan.json').read_text())
    plan['plan']['catalog']['symbols'] = ['SPY', 'FRC']
    plan['plan']['plan_sha256'] = identity({k:v for k,v in plan['plan'].items() if k != 'plan_sha256'})
    write(tmp_path/'plan.json', plan)
    active.update(plan_sha256=plan['plan']['plan_sha256'], plan_file_sha256=sha(tmp_path/'plan.json'))
    result = readiness.assess(tmp_path, write(tmp_path/'active.json', active))
    assert not next(g for g in result['gates'] if g['gate']=='rebuilt_membership')['passed']


def test_downloads_membership_and_component_tests_cannot_admit_training(tmp_path, monkeypatch):
    active = fixture(tmp_path, monkeypatch)
    path = write(tmp_path/'active.json', active)
    result = readiness.assess(tmp_path, path)
    assert not result['ready_for_training']
    assert all(g['passed'] for g in result['gates'][:3])
    assert {g['gate'] for g in result['gates'] if not g['passed']} == set(readiness.REQUIRED)


@pytest.mark.parametrize('mutation', ['none','old_scope','old_source','missing_check','partial_universe','changed_input'])
def test_full_universe_evidence_is_bound_to_scope_sources_and_checks(tmp_path, monkeypatch, mutation):
    active = fixture(tmp_path, monkeypatch)
    source = write(tmp_path/'stage-input.json', {'test':'input'})
    for name, checks in readiness.REQUIRED.items():
        directory = tmp_path/name
        report = dict(schema='v7-full-universe-evidence-v1',stage=name,
            scope_identity=readiness.scope_binding(active),symbols=['SPY'],security_ids=['spy-id'],
            checks=dict.fromkeys(checks, True),limitations=[])
        binding = dict(sources={'producer.py':'code-hash'},runtime={'python':'test-runtime'},
            source_and_input_guard='passed',inputs={str(source):sha(source)})
        if name == 'causal_prices':
            if mutation == 'old_scope': report['scope_identity'] = 'old'
            if mutation == 'old_source': binding['sources'] = {}
            if mutation == 'missing_check': report['checks'].pop(checks[0])
            if mutation == 'partial_universe': report['symbols'] = []
        write(directory/'report.json',report)
        write(directory/'binding.json',binding)
        receipt(directory, {'identity':'test-stage'})
        active['readiness_evidence'][name] = name
    path = write(tmp_path/'active.json',active)
    if mutation == 'changed_input': write(source, {'changed':True})
    result = readiness.assess(tmp_path,path)
    assert result['ready_for_training'] == (mutation == 'none')
    if mutation != 'none':
        assert not next(g for g in result['gates'] if g['gate']=='causal_prices')['passed']


@pytest.mark.parametrize('mutation',['none','wrong_stop','changed_predecessor','changed_scope'])
def test_execution_amendment_preserves_raw_scope_and_binds_option_stop(tmp_path,monkeypatch,mutation):
    active=fixture(tmp_path,monkeypatch)
    prior=dict(active,option_paper_pricing='historical-pricing.json',option_paper_pricing_sha256='historical')
    previous=write(tmp_path/'previous.json',prior)
    pricing=json.loads((tmp_path/'pricing.json').read_text())
    pricing['raw_input_predecessor']={'path':'previous.json','sha256':sha(previous)}
    if mutation=='wrong_stop':pricing['option_risk_policy']['premium_stop_fraction']=.05
    write(tmp_path/'pricing.json',pricing)
    active['option_paper_pricing_sha256']=sha(tmp_path/'pricing.json')
    if mutation=='changed_predecessor':write(previous,{**prior,'history_start':'2022-03-08'})
    if mutation=='changed_scope':active['study_scope']='Changed research restrictions'
    result=readiness.assess(tmp_path,write(tmp_path/'active.json',active))
    assert next(g['passed'] for g in result['gates'] if g['gate']=='active_inputs')==(mutation=='none')
