from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.action_inventory import candidate
from nn_meta.v7.causal_daily import returns
from nn_meta.v7.causal_prices import CausalPriceHistory, PriceAction
from nn_meta.v7.ordinary_actions import BASIS, ReconstructionAction, compile_ordinary_actions, price_action
from nn_meta.v7.storage import identity


def fixture(category='cash'):
    calendar = SessionCalendar(dict(coverage_start='2024-09-12', coverage_end='2024-09-16',
        sessions=[dict(date=d, open='09:30', close='16:00') for d in
                  ['2024-09-12', '2024-09-13', '2024-09-16']]))
    if category == 'cash':
        records = [('massive', 'dividends', dict(id='m', ticker='ABC', ex_dividend_date='2024-09-13',
                    currency='USD', cash_amount=.44)),
                   ('alpaca', 'cash_dividends', dict(id='a', symbol='ABC', ex_date='2024-09-13',
                    process_date='2024-09-16', foreign=False, rate=.44))]
    else:
        records = [('massive', 'splits', dict(id='m', ticker='ABC', execution_date='2024-09-13',
                    adjustment_type='forward_split', split_from=1, split_to=2)),
                   ('alpaca', 'forward_splits', dict(id='a', symbol='ABC', ex_date='2024-09-13',
                    old_rate=1, new_rate=2))]
    candidates = [make_candidate(*r) for r in records]
    stock = pd.DataFrame([dict(stock_ticker='ABC', source_date=day, security_id='security',
        identity_span='span', raw_close=close, observed_minutes=390,
        session_open_ns=calendar.bounds(day)[0].tz_localize('UTC').value,
        available_ns=calendar.bounds(day)[1].tz_localize('UTC').value)
        for day, close in [('2024-09-12', 40.01), ('2024-09-13', 39.50)]])
    path = Path(__file__).resolve().parents[1] / 'docs/specs/V7_ORDINARY_ACTION_ADMISSION_20260917.json'
    return candidates, [], stock, calendar, json.loads(path.read_text())


def make_candidate(provider, kind, record):
    return candidate(provider, kind, record, scoped_symbols={'ABC'},
        start='2024-09-12', end='2024-09-16', source={'receipt': 'retained', 'payload_sha256': 'hash'})


@pytest.mark.parametrize('category,factor,volume', [('cash', 1-.44/40.01, 1.), ('split', .5, 2.)])
def test_compiled_inputs_retain_assumption_and_work_in_real_causal_consumers(category, factor, volume):
    args = fixture(category)
    events, pending, decisions = compile_ordinary_actions(*args)
    assert len(events) == 1 and not pending
    event = events[0]; action = price_action(json.loads(json.dumps(event)))
    assert isinstance(action, PriceAction) and isinstance(action, ReconstructionAction)
    assert action.available_at == action.effective_at == pd.Timestamp('2024-09-13T13:30Z')
    assert action.publication_available_at is None and not action.publication_verified
    assert action.admission_basis == event['admission_basis'] == BASIS
    assert action.price_factor == pytest.approx(factor)
    assert action.volume_factor == volume
    stock, calendar = args[2:4]
    result = returns(stock, [action], calendar, security_id='security', start='2024-09-12',
        end='2024-09-13', action_evidence_identity='event-only-test')
    assert result.simple_return.iloc[-1] == pytest.approx(39.5/(40.01*factor)-1)
    index = pd.to_datetime(stock.available_ns, utc=True)-pd.Timedelta(minutes=1)
    raw = pd.DataFrame({k: stock.raw_close.to_numpy() for k in ['Open', 'High', 'Low', 'Close']}, index=index)
    raw['Volume'] = 100.; raw['available_at'] = pd.to_datetime(stock.available_ns, utc=True).to_numpy()
    history = CausalPriceHistory(raw, [action], security_id='security')
    prefix = history.view(pd.Timestamp('2024-09-12T20:00Z'))
    pd.testing.assert_frame_equal(prefix, CausalPriceHistory(raw, [], security_id='security').view(pd.Timestamp('2024-09-12T20:00Z')))
    view = history.view(pd.Timestamp('2024-09-13T20:00Z'))
    assert view.Close.iloc[0] == pytest.approx(40.01*factor)
    assert view.Close.iloc[1] == 39.5
    assert not event['full_security_admitted']
    assert decisions[0]['treatment'] == 'compiled_historical_reconstruction'


@pytest.mark.parametrize('change', ['single_provider', 'duplicate_provider', 'term_mismatch',
    'foreign', 'unknown_currency', 'simultaneous_split', 'complex', 'identity_gap',
    'missing_prior', 'missing_close', 'excess_cash', 'wrong_selected_symbol'])
def test_unsupported_events_remain_explicit_without_synthetic_factors(change):
    rows, reviews, stock, calendar, policy = fixture()
    if change == 'single_provider': rows.pop()
    if change == 'duplicate_provider':
        duplicate = deepcopy(rows[0]['record']); duplicate['id'] = 'duplicate'
        rows.append(make_candidate('massive', 'dividends', duplicate))
    if change in ('term_mismatch', 'foreign', 'unknown_currency', 'excess_cash'):
        for i, row in enumerate(rows):
            record = deepcopy(row['record'])
            if change == 'term_mismatch' and i == 0: record['cash_amount'] = .22
            if change == 'foreign' and i == 1: record['foreign'] = True
            if change == 'unknown_currency' and i == 0: record.pop('currency')
            if change == 'excess_cash': record['cash_amount' if i == 0 else 'rate'] = 100
            rows[i] = make_candidate(row['provider'], row['kind'], record)
    if change == 'simultaneous_split':
        split = dict(id='split', symbol='ABC', ex_date='2024-09-13', old_rate=1, new_rate=2)
        rows.append(make_candidate('alpaca', 'forward_splits', split))
    if change == 'complex':
        rows.append(make_candidate('alpaca', 'spin_offs', dict(id='spin', source_symbol='ABC', effective_date='2024-09-13')))
    if change == 'identity_gap': stock.loc[0, 'identity_span'] = pd.NA
    if change == 'missing_prior': stock = stock.iloc[1:]
    if change == 'missing_close': stock.loc[0, ['raw_close', 'observed_minutes']] = [float('nan'), 0]
    if change == 'wrong_selected_symbol': stock.loc[1, 'stock_ticker'] = 'OTHER'
    events, pending, decisions = compile_ordinary_actions(rows, reviews, stock, calendar, policy)
    assert events == [] and len(pending) == len(rows)
    assert all(r['compilation_reason'] for r in pending)
    assert all(d['treatment'] != 'compiled_historical_reconstruction' for d in decisions)


def test_reviewed_dvn_style_replacement_wins_exactly_once_over_matching_terms():
    rows, _, stock, calendar, policy = fixture()
    for i, row in enumerate(rows):
        record = deepcopy(row['record']); record['cash_amount' if i == 0 else 'rate'] = .22
        rows[i] = make_candidate(row['provider'], row['kind'], record)
    review = dict(event_id='reviewed', symbol='ABC', effective_date='2024-09-13',
        security_id='security', currency='USD', cash_units='per_common_share', cash_amount='.44',
        evidence_identity='issuer-review', publication_available_at='2024-09-01T12:00Z',
        replaces=[{k: r[k] for k in ['provider', 'kind', 'action_id', 'record_sha256']} for r in rows])
    events, pending, _ = compile_ordinary_actions(rows, [review], stock, calendar, policy)
    assert len(events) == 1 and not pending
    assert events[0]['admission_basis'] == 'reviewed_publication'
    assert price_action(events[0]).price_factor == pytest.approx(1-.44/40.01)
    assert not isinstance(price_action(events[0]), ReconstructionAction)


@pytest.mark.parametrize('change', ['payload', 'normalized_terms', 'duplicate_id', 'policy', 'clock'])
def test_corrupted_sources_or_policy_fail_instead_of_weakening_admission(change):
    rows, reviews, stock, calendar, policy = fixture()
    if change == 'payload': rows[0]['record']['cash_amount'] = .22
    if change == 'normalized_terms': rows[0]['term'] = '.22'
    if change == 'duplicate_id': rows.append(rows[0])
    if change == 'policy': policy['publication_verified'] = True
    if change == 'clock': stock.loc[0, 'available_ns'] += 1
    with pytest.raises(ValueError): compile_ordinary_actions(rows, reviews, stock, calendar, policy)


def test_reconstruction_cannot_be_relabelled_as_pre_event_publication():
    events, _, _ = compile_ordinary_actions(*fixture())
    action = price_action(events[0])
    for changes in [dict(available_at=action.effective_at-pd.Timedelta(days=1)),
                    dict(publication_verified=True), dict(publication_available_at='2024-09-12T12:00Z')]:
        with pytest.raises(ValueError): replace(action, **changes)
    event = deepcopy(events[0]); event['admission_policy_identity'] = 'different'
    with pytest.raises(ValueError): price_action(event)


def test_same_security_rename_uses_exact_prior_security_close_not_literal_symbol():
    args = list(fixture()); args[2].loc[0, 'stock_ticker'] = 'OLD'
    events, pending, _ = compile_ordinary_actions(*args)
    assert len(events) == 1 and not pending
    assert events[0]['evidence']['prior_stock_ticker'] == 'OLD'


def test_action_assumption_survives_feature_epoch_and_proposal_construction():
    from tests.test_v7_causal_features import fixture as chart_fixture
    from nn_meta.v7.causal_features import CausalFeatures
    from dataclasses import asdict
    expected, raw, split, calendar = chart_fixture()
    fields = asdict(split); fields['available_at'] = split.effective_at
    action = ReconstructionAction(**fields, admission_policy_identity='declared-policy')
    chart = CausalFeatures(raw, [action], calendar, security_id='fixture', minutes=1,
        start='2022-03-15', end='2022-03-16')
    assert chart.history.actions[0].admission_basis == BASIS
    for left, right in zip(chart.epochs(), expected.epochs()):
        pd.testing.assert_frame_equal(left.tv, right.tv)
        pd.testing.assert_frame_equal(left.technical, right.technical)
    pd.testing.assert_frame_equal(chart.proposal_basis(), expected.proposal_basis())
