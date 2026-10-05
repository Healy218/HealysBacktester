import json
import pytest

from nn_meta.etfe import acquisition as a, demand as d, demand_frontier as f


class EmptyHTTP:
    def get(self, *args):
        return 200, b'{"option_contracts":[],"next_page_token":null}', {}, None


def test_next_batch_balances_expiry_status_and_reuses_identity():
    _, physical = d.calendar_demand([dict(date='2026-10-02')])
    required = {k:dict(item=v) for k,v in physical.items()}
    batch, remaining = f.select_batch(required, {})
    assert len(batch) == 126 and remaining == 276
    assert {j['params']['expiration_date'] for j in batch[:6]} == {'2026-10-02'}
    assert batch[6]['params']['expiration_date'] == '2026-10-03'
    reused = {d.query_key(batch[0]): {}}
    after, remaining = f.select_batch(required, reused)
    assert batch[0] not in after and remaining == 275
    with pytest.raises(ValueError):
        f.select_batch(required, {}, 127)


def test_surface_zero_five_fortyfive_and_early_close_unknown_is_not_zero():
    calendar = [dict(date='2026-10-02', open='09:30', close='13:00')]
    _, physical = d.calendar_demand(calendar)
    required = {k:dict(item=v) for k,v in physical.items()}
    contracts = {str(i):dict(ticker='SPY', expiry=expiry) for i,expiry in enumerate(
        ['2026-10-02', '2026-10-07', '2026-10-08', '2026-11-16', '2026-11-17'])}
    result = f.surface_envelope(calendar, contracts, {}, required)
    spy, qqq, voo = result
    assert spy['returned_symbol_surface'] == 4
    assert spy['returned_purchase_symbols'] == 2
    assert spy['one_bar_per_regular_minute_scenario'] == 4*210
    assert spy['gross_surface_requests'] == 1
    assert qqq['returned_symbol_surface'] == 0
    assert all(s['unresolved_discovery_queries'] == 92 for s in result)


def test_frontier_verifies_payload_and_does_not_admit_empty_history(tmp_path):
    item = d.discovery_job('SPY', '2024-01-19', 'inactive')
    root = tmp_path/'raw'
    a.prepare(root, [item])
    with pytest.raises(ValueError, match='Complete'):
        f.inspect_inputs([root])
    a.capture(root, EmptyHTTP(), sleep=lambda _:None, check_resources=lambda *_:None)
    _, queries, contracts, measures = f.inspect_inputs([root])
    assert len(queries) == 1 and not contracts
    assert measures['contracts']['empty_queries'] == 1
    assert measures['contracts']['pages'] == 1
    with pytest.raises(ValueError, match='Duplicate'):
        f.inspect_inputs([root, root])
    next((root/'attempts').glob('*/body.json')).write_text('{}')
    with pytest.raises(ValueError, match='checksum'):
        f.inspect_inputs([root])


def test_request_reservation_survives_network_crash_and_resume(tmp_path, monkeypatch):
    item = d.discovery_job('SPY', '2024-01-19', 'inactive')
    root = tmp_path/'raw'
    a.prepare(root, [item], parent=dict(kind='etfe-demand-frontier-discovery',
        frontier_root='fixture', frontier_sha256='bound', max_total_requests=256))
    monkeypatch.setattr(f, 'load', lambda _:dict(sha256='bound', next_discovery_jobs=[item]))
    class CrashHTTP:
        def get(self, *args):
            raise OSError('simulated network process death')
    kwargs = dict(sleep=lambda _:None, check_resources=lambda *_:None)
    with pytest.raises(OSError):
        f.run(root, CrashHTTP(), **kwargs)
    assert len(list((root/'request_reservations').glob('*'))) == 1
    result = f.run(root, EmptyHTTP(), **kwargs)
    assert result['capture_complete'] and result['requests_this_run'] == 1
    again = f.run(root, EmptyHTTP(), **kwargs)
    assert again['requests_this_run'] == 0
    assert len(list((root/'request_reservations').glob('*'))) == 2


def test_total_study_budget_cannot_reset_between_invocations(tmp_path, monkeypatch):
    item = d.discovery_job('SPY', '2024-01-19', 'inactive')
    root = tmp_path/'raw'
    a.prepare(root, [item], parent=dict(kind='etfe-demand-frontier-discovery',
        frontier_root='fixture', frontier_sha256='bound', max_total_requests=256))
    monkeypatch.setattr(f, 'load', lambda _:dict(sha256='bound', next_discovery_jobs=[item]))
    reservations = root/'request_reservations'
    reservations.mkdir()
    for i in range(256):
        (reservations/f'{i:06d}.json').write_text('{}')
    with pytest.raises(ValueError, match='exhausted'):
        f.run(root, EmptyHTTP())
