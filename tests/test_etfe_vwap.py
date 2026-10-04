import copy
import json

import pytest

from nn_meta.etfe.vwap_reference import BASIS, reference_from_bar
from nn_meta.etfe.vwap_setup import expected_scope, validate_scope


@pytest.fixture
def bar():
    return dict(t='2026-10-02T13:30:00Z', o=2.0, h=3.0, l=1.0, c=2.5,
                vw=2.25, v=20, n=5)


def test_uses_vwap_and_never_range_midpoint(bar):
    result = reference_from_bar(bar, as_of='2026-10-02T13:31:01Z')
    assert result['price'] == 2.25 != (bar['h']+bar['l'])/2
    assert result['basis'] == BASIS
    assert result['executable_fill_verified'] is False
    assert result['original_revision_timing_verified'] is False
    assert result['availability_basis'] == 'modeled_end_plus_1s'


@pytest.mark.parametrize('as_of', ['2026-10-02T13:30:59Z','2026-10-02T13:31:00Z',
                                  '2026-10-02T13:31:00.999999Z'])
def test_bar_cannot_leak_into_its_own_minute_or_preavailability_decision(bar, as_of):
    assert reference_from_bar(bar, as_of=as_of) is None


def test_late_arrival_is_honored(bar):
    assert reference_from_bar(bar, as_of='2026-10-02T13:31:01Z',
                              available_at='2026-10-02T13:31:05Z') is None
    result = reference_from_bar(bar, as_of='2026-10-02T13:31:05Z',
                                available_at='2026-10-02T13:31:05Z')
    assert result['availability_basis'] == 'captured_with_minimum_lag'
    assert reference_from_bar(bar, as_of='2026-10-02T13:30:59Z',
                              available_at='2026-10-02T13:30:30Z') is None


def test_staleness_boundaries_and_missing_minutes(bar):
    assert reference_from_bar(bar, as_of='2026-10-02T13:32:00Z')['price'] == 2.25
    assert reference_from_bar(bar, as_of='2026-10-02T13:32:00.000001Z') is None
    assert reference_from_bar(None, as_of='2026-10-02T13:32:01Z') is None


@pytest.mark.parametrize('field,value', [('vw',None),('vw',0),('vw',float('nan')),
    ('vw',float('inf')),('vw',True),('v',0),('n',0),('n',1.2),('v',-3)])
def test_invalid_bars_never_fall_back_to_ohlc(bar, field, value):
    bar[field] = value
    with pytest.raises(ValueError):
        reference_from_bar(bar, as_of='2026-10-02T13:31:01Z')


def test_timezones_and_minute_alignment(bar):
    result = reference_from_bar(bar, as_of='2026-10-02T09:31:01-04:00')
    assert result['as_of'] == '2026-10-02T13:31:01+00:00'
    with pytest.raises(ValueError, match='timezone-aware'):
        reference_from_bar(bar, as_of='2026-10-02T13:31:01')
    bar['t'] = '2026-10-02T13:30:01Z'
    with pytest.raises(ValueError, match='minute-aligned'):
        reference_from_bar(bar, as_of='2026-10-02T13:31:01Z')


def test_changed_method_preserves_other_scope_and_risk():
    from nn_meta.etfe.preparation import SCOPE
    old = json.loads(SCOPE.read_text())
    new = expected_scope()
    validate_scope(new)
    assert 'quote_policy' not in new
    for key in ('history','symbols','signal_minutes','dte_targets','evaluation'):
        assert new[key] == old[key]
    for key in ('fee','slippage','latency_ns','entry_deadline_ns','multiplier'):
        assert new['pricing_policy'][key] == old['quote_policy'][key]
    assert new['risk_policy']['premium_stop_fraction'] == .125
    assert new['risk_policy']['expiry_exit_before_close_minutes'] == 15
    assert new['pricing_policy']['fallback'] is None


@pytest.mark.parametrize('target', ['fallback','basis','ready','features'])
def test_implicit_policy_changes_rejected(target):
    scope = copy.deepcopy(expected_scope())
    if target in ('fallback','basis'):
        scope['pricing_policy'][target] = 'high_low_midpoint'
    elif target == 'ready':
        scope['ready_for_build'] = True
    else:
        scope['feature_scope']['replacement'] = 'zero_fill_quotes'
    with pytest.raises(ValueError):
        validate_scope(scope)


@pytest.fixture
def vwap_setup(tmp_path):
    from nn_meta.etfe.preparation import digest, file_sha, save_new
    from nn_meta.etfe.vwap_setup import SCOPE
    root = tmp_path/'repo'
    folder = root/'setup'
    folder.mkdir(parents=True)
    declared = root/'docs/specs'/SCOPE.name
    declared.parent.mkdir(parents=True)
    declared.write_bytes(SCOPE.read_bytes())
    (root/'producer.py').write_text('# immutable source\n')
    (folder/'source-snapshot').mkdir()
    (folder/'source-snapshot/producer.py').write_bytes((root/'producer.py').read_bytes())
    scope = expected_scope()
    catalog = dict(expert='etfe',symbols=scope['symbols'],signal_minutes=scope['signal_minutes'],
                   ticker_variant_combinations=3,ready_for_build=False)
    catalog['catalog_sha256'] = digest(catalog)
    plan = dict(schema='etfe-setup-plan-v2',expert='etfe',scope=scope,
        scope_sha256=file_sha(declared),catalog_sha256=catalog['catalog_sha256'],
        runtime=dict(pool='etfe',provider='alpaca',feed='opra',state_root=str(folder)),
        readiness=dict(ready_for_build=False,ready_for_training=False),
        source_bindings={'producer.py':file_sha(root/'producer.py')})
    plan['plan_sha256'] = digest(plan)
    for name, obj in [('scope.json',scope),('plan.json',plan),('catalog.json',catalog)]:
        save_new(folder/name,obj)
    save_new(folder/'PREPARED.json',dict(schema='etfe-preparation-receipt-v2',expert='etfe',
        status='prepared_not_admitted',ready_for_build=False,ready_for_training=False,
        plan_sha256=plan['plan_sha256'],source_snapshot=plan['source_bindings'],
        files={n:file_sha(folder/n) for n in ('scope.json','plan.json','catalog.json')}))
    return root, folder


def test_vwap_integrity_does_not_imply_admission(vwap_setup):
    from nn_meta.etfe.vwap_setup import verify
    root, folder = vwap_setup
    result = verify(folder,source_root=root)
    assert result['ready_for_build'] is False and result['ready_for_training'] is False


@pytest.mark.parametrize('target', ['producer.py','setup/source-snapshot/producer.py','setup/catalog.json'])
def test_vwap_integrity_rejects_artifact_or_source_changes(vwap_setup,target):
    from nn_meta.etfe.vwap_setup import verify
    root, folder = vwap_setup
    p = root/target
    p.write_text(p.read_text()+'\n')
    with pytest.raises(ValueError):
        verify(folder,source_root=root)
