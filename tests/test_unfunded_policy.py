"""A rejected cash allocation is a policy outcome; invalid data still stops work."""
import json

import numpy as np
import pandas as pd
import pytest

from nn_meta import v4_evaluate as evaluate
from nn_meta.v4_accounting import (AccountingDataError, UnfundedEntryError,
                                    CostScenario, mark_to_market_portfolio)
from nn_meta.execution_validation import checked_ledger


def cash_exhaustion_book():
    # A appreciates before B enters. B consumes all remaining cash, while
    # positive NAV remains in A/B. C cannot be funded without borrowing.
    trades = pd.DataFrame(dict(trade_id=['a', 'b', 'c'], symbol=['AA', 'BB', 'CC'],
        signal_ts=pd.to_datetime(['2026-01-02 14:15', '2026-01-02 14:45', '2026-01-02 15:00']),
        fill_entry_ts=pd.to_datetime(['2026-01-02 14:30', '2026-01-02 15:00', '2026-01-02 15:15']),
        fill_exit_ts=pd.to_datetime(['2026-01-02 16:00'] * 3), gross_return=[0., 0., 0.]))
    marks = pd.DataFrame([('a', '14:30', 0.), ('a', '15:00', 100.), ('a', '16:00', 0.),
                          ('b', '15:00', 0.), ('b', '16:00', 0.),
                          ('c', '15:15', 0.), ('c', '16:00', 0.)],
                         columns=['trade_id', 'mark_ts', 'gross_return'])
    marks['mark_ts'] = pd.to_datetime('2026-01-02 ' + marks.mark_ts)
    return trades, marks


def test_cash_guard_is_strict_even_with_positive_unrealized_equity():
    trades, marks = cash_exhaustion_book()
    with pytest.raises(UnfundedEntryError) as error:
        mark_to_market_portfolio(trades, marks, max_concurrent=5, position_fraction=.1,
                                costs=CostScenario(fee=0, slippage=0))
    assert error.value.details == dict(reason='unfunded_entry', timestamp='2026-01-02 15:15:00',
                                      trade_id='c', cash=0., equity=pytest.approx(11.))


def test_independent_rejection_is_reported_without_a_fake_return():
    trades, marks = cash_exhaustion_book()
    with pytest.raises(UnfundedEntryError):
        checked_ledger(trades, marks, max_concurrent=5, position_fraction=.1, costs=CostScenario())
    metrics, curve = checked_ledger(trades, marks, max_concurrent=5, position_fraction=.1,
                                    costs=CostScenario(), allow_unfunded=True)
    assert metrics['total_return'] is None and metrics['max_drawdown'] is None
    assert not metrics['independent_ledger_match'] and metrics['independent_rejection_match']
    assert metrics['accounting_status'] == 'unfunded' and metrics['selected_positions'] == 3
    assert curve.empty


def test_report_mode_does_not_swallow_invalid_marks():
    trades, marks = cash_exhaustion_book()
    marks.loc[0, 'gross_return'] = np.nan
    with pytest.raises(AccountingDataError, match='finite'):
        checked_ledger(trades, marks, max_concurrent=5, position_fraction=.1,
                       costs=CostScenario(), allow_unfunded=True)


def test_policy_search_rejects_only_unfundable_candidates(monkeypatch):
    from tests.test_v4_evaluate import _flip_fixture
    rows, pred, stream, spec = _flip_fixture()
    original = evaluate.mark_to_market_portfolio
    calls = 0
    def reject_one(trades, marks, **kwargs):
        nonlocal calls
        calls += 1
        # Baseline and its outlier check run first; fail one candidate book.
        if calls == 3:
            raise UnfundedEntryError(timestamp='2026-05-21', trade_id='c', cash=0, equity=.7)
        return original(trades, marks, **kwargs)
    monkeypatch.setattr(evaluate, 'mark_to_market_portfolio', reject_one)
    result = evaluate.choose_policy(rows, pred, spec, thresholds=[.5, .88], mark_stream=stream)
    rejected = [c for c in result['candidate_grid'] if c.get('accounting_status') == 'unfunded']
    assert len(rejected) == 1
    assert rejected[0]['eligible'] is False and rejected[0]['total_return'] is None
    assert result['metrics'].get('accounting_status') != 'unfunded'
    json.dumps(result, default=evaluate._json_default)


def test_unfundable_baseline_never_waives_the_gate(monkeypatch):
    from tests.test_v4_evaluate import _flip_fixture
    rows, pred, stream, spec = _flip_fixture()
    original = evaluate.mark_to_market_portfolio
    calls = 0
    def reject_baseline(trades, marks, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise UnfundedEntryError(timestamp='2026-05-21', trade_id='c', cash=0, equity=.7)
        return original(trades, marks, **kwargs)
    monkeypatch.setattr(evaluate, 'mark_to_market_portfolio', reject_baseline)
    result = evaluate.choose_policy(rows, pred, spec, thresholds=[.5], mark_stream=stream, report_all_gates=True)
    assert not result['eligible'] and result['baseline_accounting_failure']['reason'] == 'unfunded_entry'
    assert all(not any(c['eligible_by_gate'].values()) for c in result['candidate_grid'])


def test_policy_search_does_not_swallow_accounting_corruption(monkeypatch):
    from tests.test_v4_evaluate import _flip_fixture
    rows, pred, stream, spec = _flip_fixture()
    def invalid(*args, **kwargs):
        raise AccountingDataError('terminal mark disagrees')
    monkeypatch.setattr(evaluate, 'mark_to_market_portfolio', invalid)
    with pytest.raises(AccountingDataError, match='terminal mark disagrees'):
        evaluate.choose_policy(rows, pred, spec, thresholds=[.5], mark_stream=stream)


def test_marked_test_rejection_has_no_performance_and_report_renders(monkeypatch, tmp_path):
    from tests.test_v4_evaluate import _flip_fixture
    rows, pred, stream, spec = _flip_fixture()
    def reject(*args, **kwargs):
        raise UnfundedEntryError(timestamp='2026-05-21', trade_id='c', cash=0, equity=.7)
    monkeypatch.setattr(evaluate, 'mark_to_market_portfolio', reject)
    marked = evaluate.marked_metrics(rows, pred, 'rank', .5, stream)
    assert marked['total_return'] is None and marked['accounting_status'] == 'unfunded'
    result = {'schema': 'v4', 'purged': True, 'winner': dict(family='nn', mode='rank',
        threshold=.5, eligible=False, test={'total_return': .1, 'max_drawdown': .2}, marked=marked)}
    output = tmp_path / 'report.md'
    evaluate._write_report([result], output)
    assert 'infeasible: unfunded entry (no marked return)' in output.read_text()


def test_aggregate_revalidation_preserves_original_drawdown_brake(tmp_path):
    from tests.test_v4_evaluate import _flip_fixture
    from scripts.validate_v6_execution import frozen_selections, config_feature_contract
    from nn_meta.mark_stream import stable_trade_id
    rows, pred, _, spec = _flip_fixture()
    rows['trade_id'] = stable_trade_id(rows)
    rows['contract'] = 'SPY250131C00500000'
    rows['expiration'] = pd.Timestamp('2025-01-31')
    for folder in ('model_final', 'reports', 'artifacts'):
        (tmp_path / folder).mkdir()
    rows.to_parquet(tmp_path / 'artifacts/meta_dataset.parquet', index=False)
    rows.assign(pred_ensemble=pred, ev_ensemble=pred).to_parquet(
        tmp_path / 'reports/finalize_val_predictions.parquet', index=False)
    (tmp_path / 'artifacts/baseline_spec.json').write_text(json.dumps(spec))
    cfg = dict(mode='ev', family='nn', threshold=.05, dd_brake=.3,
               feature_contract_version=config_feature_contract())
    model = tmp_path / 'model_final/ensemble_config.json'
    model.write_text(json.dumps(cfg))
    braked, policy = frozen_selections(tmp_path)
    model.write_text(json.dumps(dict(cfg, dd_brake=None)))
    unbraked, _ = frozen_selections(tmp_path)
    assert policy['dd_brake'] == .3 and 'frozen original-policy' in policy['sizing']
    assert braked['candidate'].size_fraction.min() < unbraked['candidate'].size_fraction.min()


def test_independent_disagreement_cannot_be_reported_as_matched_rejection(monkeypatch):
    from nn_meta import execution_validation
    trades, marks = cash_exhaustion_book()
    monkeypatch.setattr(execution_validation, 'independent_ledger', lambda *a, **kw: pd.DataFrame())
    with pytest.raises(AccountingDataError, match='unexpectedly funds'):
        checked_ledger(trades, marks, max_concurrent=5, position_fraction=.1,
                       costs=CostScenario(), allow_unfunded=True)
