import numpy as np
import pandas as pd
import pytest

from nn_meta.multitimeframe_catalog import registered_catalog
from nn_meta.v7.context import chart_context
from nn_meta.v7.features import technical
from nn_meta.v7.rows import FeatureRows, schema, DAILY, FEATURE_NAMES, NUMERIC_FEATURES


def fixture():
    index = pd.date_range('2022-03-07T14:30Z', periods=120, freq='min')
    close = np.arange(120) + 100.
    bars = pd.DataFrame({'Open': close, 'High': close + 1, 'Low': close - 1, 'Close': close, 'Volume': 100.}, index=index)
    calendar = {'timezone': 'America/New_York', 'coverage_start': '2022-03-07', 'coverage_end': '2022-03-07',
                'sessions': [{'date': '2022-03-07', 'open': '09:30', 'close': '16:00'}]}
    context = chart_context(bars, bars, calendar, 1)
    tv = pd.DataFrame(0., index=index, columns=FEATURE_NAMES)
    daily = pd.DataFrame([{**dict.fromkeys(DAILY, .2), 'source_date': '2022-03-04', 'security_id': 'SPY-id'}],
                         index=pd.DatetimeIndex(['2022-03-07T14:30Z']))
    variant = next(r for r in registered_catalog(['SPY'])['records'] if r['strategy'] == 'ma' and r['signal_minutes'] == 1)
    clock = index[100]
    ticks = {**dict.fromkeys(NUMERIC_FEATURES, .3), 'option_tick_status': 'covered', 'symbol': 'SPY',
             'contract': 'SPY220309C00420000', 'window_start_ns': clock.value,
             'window_end_ns': clock.value + 60_000_000_000, 'decision_close_ns': clock.value + 60_000_000_000}
    return bars, context, technical(bars, context), tv, daily, variant, clock, ticks


def test_full_schema_includes_original_features_and_actual_ma_parameter_values():
    bars, context, tech, tv, daily, variant, clock, ticks = fixture()
    builder = FeatureRows(bars, context, tech, tv, daily, symbol='SPY', security_id='SPY-id', sector='idx_etf')
    row = builder.row(variant=variant, bar_at=clock, right='C', target_dte=1, bars_since_previous_signal=7,
                      ticks=ticks, raw_spot=400., raw_spot_available_ns=ticks['decision_close_ns'])
    fast, slow = variant['params']['fast_window'], variant['params']['slow_window']
    assert len(row) == len(set(schema())) == 222
    assert row.ma_gap == pytest.approx((bars.Close.rolling(fast).mean()[clock] - bars.Close.rolling(slow).mean()[clock]) / bars.Close[clock])
    assert row.ma_gap != tech.ma_gap[clock]
    assert row.param_fast_window == fast and row.param_slow_window == slow
    assert row.timeframe_1 == 1 and row.timeframe_5 == 0 and row.sec_idx_etf == 1
    assert row.dte_frac == pytest.approx(2 / 9)
    assert row.moneyness == pytest.approx(np.log(420 / 400))
    assert row.attrs['actual_dte'] == 2 and row.attrs['target_dte'] == 1


def test_same_day_daily_features_and_wrong_contract_direction_are_rejected():
    bars, context, tech, tv, daily, variant, clock, ticks = fixture()
    daily.source_date = '2022-03-07'
    builder = FeatureRows(bars, context, tech, tv, daily, symbol='SPY', security_id='SPY-id', sector=None)
    with pytest.raises(ValueError, match='prior-date'):
        builder.row(variant=variant, bar_at=clock, right='C', target_dte=1, bars_since_previous_signal=0,
                    ticks=ticks, raw_spot=400., raw_spot_available_ns=ticks['decision_close_ns'])
    daily.source_date = '2022-03-04'
    with pytest.raises(ValueError, match='direction'):
        builder.row(variant=variant, bar_at=clock, right='P', target_dte=1, bars_since_previous_signal=0,
                    ticks=ticks, raw_spot=400., raw_spot_available_ns=ticks['decision_close_ns'])


@pytest.mark.parametrize('offset,spot', [(1, 400.), (-60_000_000_001, 400.), (0, float('nan')), (0, 0.)])
def test_raw_spot_must_be_fresh_causal_and_positive(offset, spot):
    bars, context, tech, tv, daily, variant, clock, ticks = fixture()
    builder = FeatureRows(bars, context, tech, tv, daily, symbol='SPY', security_id='SPY-id', sector=None)
    with pytest.raises(ValueError, match='raw spot'):
        builder.row(variant=variant, bar_at=clock, right='C', target_dte=1, bars_since_previous_signal=0,
                    ticks=ticks, raw_spot=spot, raw_spot_available_ns=ticks['decision_close_ns']+offset)


def test_weekend_dte_uses_calendar_days_and_rejects_expired_contract():
    bars, context, tech, tv, daily, variant, clock, ticks = fixture()
    builder = FeatureRows(bars, context, tech, tv, daily, symbol='SPY', security_id='SPY-id', sector=None)
    ticks['contract'] = 'SPY220311C00420000'
    row = builder.row(variant=variant, bar_at=clock, right='C', target_dte=1, bars_since_previous_signal=0,
                      ticks=ticks, raw_spot=400., raw_spot_available_ns=ticks['decision_close_ns'])
    assert row.dte_frac == pytest.approx(4 / 9)
    ticks['contract'] = 'SPY220307C00420000'
    with pytest.raises(ValueError, match='calendar DTE'):
        builder.row(variant=variant, bar_at=clock, right='C', target_dte=1, bars_since_previous_signal=0,
                    ticks=ticks, raw_spot=400., raw_spot_available_ns=ticks['decision_close_ns'])


def test_initial_daily_warmup_keeps_rows_with_explicit_missing_values():
    bars, context, tech, tv, daily, variant, clock, ticks = fixture()
    daily.index = daily.index + pd.Timedelta(days=1)
    builder = FeatureRows(bars, context, tech, tv, daily, symbol='SPY', security_id='SPY-id', sector=None)
    row = builder.row(variant=variant, bar_at=clock, right='C', target_dte=1, bars_since_previous_signal=0,
                      ticks=ticks, raw_spot=400., raw_spot_available_ns=ticks['decision_close_ns'])
    assert row[list(DAILY)].isna().all()
    assert row.attrs['daily_context_status'] == 'warmup_unavailable'
    assert row.attrs['daily_available_at'] is None


def test_rows_consume_security_bound_dated_sectors_and_retain_provenance():
    from nn_meta.v7.sectors import DatedSectors
    bars, context, tech, tv, daily, variant, clock, ticks = fixture()
    history = pd.DataFrame([dict(date='2022-03-07', security_id='SPY-id', sector='idx_etf',
        available_ns=bars.index[0].value, reference_date='2022-03-04', reason='dated_fund',
        source_receipt='fixture', source_sha256='digest')])
    sectors = DatedSectors(history, security_id='SPY-id')
    builder = FeatureRows(bars, context, tech, tv, daily, symbol='SPY', security_id='SPY-id', sector=sectors)
    row = builder.row(variant=variant, bar_at=clock, right='C', target_dte=1, bars_since_previous_signal=0,
                      ticks=ticks, raw_spot=400., raw_spot_available_ns=ticks['decision_close_ns'])
    assert row.sec_idx_etf == 1 and row.filter(like='sec_').sum() == 1
    assert row.attrs['sector_context']['reference_date'] == '2022-03-04'
    assert row.attrs['sector_context_status'] == 'dated'
    history['sector'] = None
    builder.sector = DatedSectors(history, security_id='SPY-id')
    row = builder.row(variant=variant, bar_at=clock, right='C', target_dte=1, bars_since_previous_signal=0,
                      ticks=ticks, raw_spot=400., raw_spot_available_ns=ticks['decision_close_ns'])
    assert row.filter(like='sec_').sum() == 0
    assert row.attrs['sector_context']['sector'] is None
