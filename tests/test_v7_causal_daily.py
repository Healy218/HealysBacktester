import numpy as np
import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.causal_daily import FEATURES, context, missingness, returns, timeline
from nn_meta.v7.causal_prices import CausalPriceHistory, PriceAction


def fixture(count=85):
    days = pd.bdate_range('2022-03-15', periods=count + 1).strftime('%Y-%m-%d').tolist()
    calendar = SessionCalendar(dict(coverage_start=days[0], coverage_end=days[-1],
        sessions=[dict(date=d, open='09:30', close='13:00' if i == 10 else '16:00')
                  for i, d in enumerate(days)]))
    clock = timeline(calendar, days[0], days[-2])
    prices = 100 * np.exp(np.cumsum(.001 + .01 * np.sin(np.arange(count))))
    stock = pd.DataFrame(dict(source_date=days[:-1], raw_close=prices,
        observed_minutes=390, available_ns=clock.stock_available_ns, identity_span='span-a'))
    surface = pd.DataFrame(dict(source_date=days[:-1], atm_iv_near=.3 + np.arange(count) * .001,
        atm_iv_far=.35 + np.arange(count) * .001, pc_ratio=1., capture_complete=True,
        available_ns=clock.available_ns))
    return stock, surface, calendar


def calculate(stock, calendar, actions=(), security_id='security'):
    return returns(stock, actions, calendar, security_id=security_id,
        start=stock.source_date.iloc[0], end=stock.source_date.iloc[-1],
        action_evidence_identity='reviewed-inventory')


def event(stock, calendar, position, factor):
    effective = calendar.bounds(stock.source_date.iloc[position])[0].tz_localize('UTC')
    return PriceAction(str(position), effective, effective - pd.Timedelta(days=1),
                       factor, 1., 'reviewed-original')


def test_action_returns_match_independent_asof_chart_including_combined_event():
    stock, _, calendar = fixture()
    actions = [event(stock, calendar, i, factor) for i, factor in [(10, .5), (30, .99), (50, .49)]]
    for action in actions:
        day = action.effective_at.tz_convert('America/New_York').date().isoformat()
        stock.loc[stock.source_date.ge(day), 'raw_close'] *= action.price_factor
    result = calculate(stock, calendar, actions)
    raw_index = pd.to_datetime(stock.available_ns, utc=True) - pd.Timedelta(minutes=1)
    raw = pd.DataFrame({name: stock.raw_close.to_numpy() for name in ['Open', 'High', 'Low', 'Close']},
                       index=pd.DatetimeIndex(raw_index))
    raw['Volume'] = 100.
    raw['available_at'] = pd.to_datetime(stock.available_ns, utc=True).to_numpy()
    history = CausalPriceHistory(raw, actions, security_id='security')
    for i in range(1, len(stock)):
        view = history.view(pd.Timestamp(stock.available_ns.iloc[i], tz='UTC'))
        expected = view.Close.iloc[-1] / view.Close.iloc[-2] - 1
        assert result.simple_return.iloc[i] == pytest.approx(expected, abs=2e-15)
    assert result.simple_return.iloc[0] is np.nan or np.isnan(result.simple_return.iloc[0])


def test_missing_day_and_identity_break_reset_return_and_rolling_warmup():
    stock, surface, calendar = fixture()
    stock.loc[12, ['raw_close', 'observed_minutes']] = [np.nan, 0]
    stock.loc[35, 'identity_span'] = None
    stock.loc[36:, 'identity_span'] = 'span-b'
    result = calculate(stock, calendar)
    assert result.return_status.iloc[12:14].tolist() == ['no_stock_observation', 'missing_prior_session']
    assert result.return_status.iloc[35:37].tolist() == ['unknown_identity', 'continuity_start']
    assert result.simple_return.iloc[[0, 12, 13, 35, 36]].isna().all()
    assert result.rvol_5.iloc[12:18].isna().all()
    assert np.isfinite(result.rvol_5.iloc[18])
    assert result.rvol_21.iloc[35:57].isna().all()
    assert np.isfinite(result.rvol_21.iloc[57])
    output = context(result, surface, is_market=True)
    assert output.atm_iv_near.iloc[35:36].isna().all()
    assert output.iv_chg_5.iloc[35:41].isna().all()
    assert np.isfinite(output.iv_chg_5.iloc[41])
    stock.loc[36:, 'identity_span'] = 'span-a'
    with pytest.raises(ValueError, match='Disjoint'):
        calculate(stock, calendar)


def test_prefix_is_unchanged_by_later_prices_actions_and_surfaces():
    stock, surface, calendar = fixture()
    before = context(calculate(stock.iloc[:65], calendar), surface.iloc[:65], is_market=True)
    action = event(stock, calendar, 70, .5)
    stock.loc[70:, 'raw_close'] *= .5
    surface.loc[70:, 'atm_iv_near'] = 2.
    full = context(calculate(stock, calendar, [action]), surface, is_market=True)
    pd.testing.assert_frame_equal(before, full.iloc[:65])
    assert before.index[10] == pd.Timestamp(surface.available_ns.iloc[10], tz='UTC')
    assert before.index[0] == calendar.bounds(stock.source_date.iloc[1])[0].tz_localize('UTC')


def test_surface_absence_stays_missing_and_beta_uses_explicit_market():
    stock, surface, calendar = fixture()
    market = context(calculate(stock, calendar, security_id='market'), surface, is_market=True)
    other = stock.copy()
    market_simple = np.expm1(np.diff(np.log(stock.raw_close)))
    other.raw_close = np.r_[100., 100 * np.cumprod(1 + 2 * market_simple)]
    surface.loc[65, ['atm_iv_near', 'atm_iv_far', 'pc_ratio']] = np.nan
    surface.loc[64, 'pc_ratio'] = 8.
    result = context(calculate(other, calendar), surface, market=market)
    assert result.beta_60d.iloc[-1] == pytest.approx(2., abs=1e-10)
    assert result.loc[:, list(FEATURES)].shape[1] == 10
    assert result.atm_iv_near.iloc[65:66].isna().all()
    assert np.isnan(result.iv_chg_5.iloc[70])
    assert result.pc_ratio.iloc[64] == 5.
    assert result.market_iv.iloc[65] == market.atm_iv_near.iloc[65]
    report = missingness(result)
    assert report['beta_60d']['first_source_date'] == stock.source_date.iloc[60]
    assert report['rvol_21']['first_source_date'] == stock.source_date.iloc[21]
    assert report['rvol_5']['first_available_at'] == result.index[5].isoformat()


@pytest.mark.parametrize('failure', ['missing_day', 'clock', 'price', 'evidence', 'mid_session', 'duplicate_event'])
def test_reject_unreviewable_stock_or_action_inputs(failure):
    stock, _, calendar = fixture()
    actions = []
    if failure == 'missing_day': stock = stock.drop(20)
    if failure == 'clock': stock.loc[20, 'available_ns'] += 1
    if failure == 'price': stock.loc[20, 'raw_close'] = np.nan
    if failure == 'evidence':
        with pytest.raises(ValueError, match='evidence'):
            returns(stock, [], calendar, security_id='x', start=stock.source_date.iloc[0],
                end=stock.source_date.iloc[-1], action_evidence_identity='')
        return
    if failure == 'mid_session':
        action = event(stock, calendar, 20, .5)
        actions = [PriceAction(action.event_id, action.effective_at + pd.Timedelta(minutes=1),
                               action.available_at, .5, 2., action.source_identity)]
    if failure == 'duplicate_event': actions = [event(stock, calendar, 20, .5)] * 2
    with pytest.raises(ValueError): calculate(stock, calendar, actions)


@pytest.mark.parametrize('failure', ['missing_day', 'clock', 'identity', 'capture', 'infinite'])
def test_reject_surface_misalignment_instead_of_filling(failure):
    stock, surface, calendar = fixture()
    if failure == 'missing_day': surface = surface.drop(20)
    if failure == 'clock': surface.loc[20, 'available_ns'] += 1
    if failure == 'identity': surface['security_id'] = 'someone-else'
    if failure == 'capture': surface.loc[20, 'capture_complete'] = False
    if failure == 'infinite': surface.loc[20, 'atm_iv_near'] = np.inf
    with pytest.raises(ValueError): context(calculate(stock, calendar), surface, is_market=True)


def test_no_calendar_extension_or_market_silently_invented():
    stock, surface, calendar = fixture()
    with pytest.raises(ValueError, match='next-session'):
        timeline(calendar, calendar.start, calendar.end)
    with pytest.raises(ValueError, match='market context'):
        context(calculate(stock, calendar), surface)
    market = context(calculate(stock, calendar), surface, is_market=True).iloc[1:]
    with pytest.raises(ValueError, match='Market dates'):
        context(calculate(stock, calendar), surface, market=market)


def test_nullable_identity_spans_keep_unknown_days_and_break_continuity():
    stock, surface, calendar = fixture()
    stock.identity_span = stock.identity_span.astype('string')
    stock.loc[35, 'identity_span'] = pd.NA
    stock.loc[36:, 'identity_span'] = 'span-b'
    result = calculate(stock, calendar)
    assert result.return_status.iloc[35:37].tolist() == ['unknown_identity', 'continuity_start']
    assert result.simple_return.iloc[35:37].isna().all()
    output = context(result, surface, is_market=True)
    assert output.iv_chg_5.iloc[35:41].isna().all()
