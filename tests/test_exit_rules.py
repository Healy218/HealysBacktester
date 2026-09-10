from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

from nn_meta.live.exit_rules import format_exit_line, strategy_exit

NOW = datetime(2026, 9, 9, 18, tzinfo=timezone.utc)
RSI = dict(rsi_window=14, entry_threshold=35, exit_threshold=70)

@pytest.mark.parametrize('family,params,long_rule,short_rule', [
    ('ma', dict(fast_window=10, slow_window=30), 'MA(10) crosses below MA(30)', 'MA(10) crosses above MA(30)'),
    ('rsi', RSI, 'RSI(14) crosses below 70', 'RSI(14) crosses above 35'),
    ('macd', dict(macd_fast_window=12, macd_slow_window=26, macd_signal_window=9), 'MACD(12,26) crosses below signal(9)', 'MACD(12,26) crosses above signal(9)'),
    ('bbands', dict(bb_window=20), 'close crosses below Bollinger middle band(20)', 'close crosses above Bollinger middle band(20)'),
    ('stoch', dict(stoch_k_window=14, stoch_d_window=3, overbought=80, oversold=20), 'stochastic(14,3) %K crosses below %D with %K > 80', 'stochastic(14,3) %K crosses above %D with %K < 20'),
    ('supertrend', dict(st_window=10, st_mult=3), 'Supertrend(10,3) flips down', 'Supertrend(10,3) flips up'),
    ('tv_rating', dict(exit_rating=-.2), 'technical rating crosses below -0.2', 'technical rating crosses above 0.2'),
    ('squeeze', {}, 'squeeze momentum crosses below zero', 'squeeze momentum crosses above zero'),
    ('keltner', dict(kc_window=20), 'close crosses below Keltner EMA(20)', 'close crosses above Keltner EMA(20)'),
    ('bbw_squeeze', dict(bbw_window=20), 'close crosses below Bollinger SMA(20)', 'close crosses above Bollinger SMA(20)'),
    ('elliott', dict(swing_order=5), 'close reaches latest swing high or low in up-swing regime (order 5)', 'close reaches latest swing high or low in down-swing regime (order 5)'),
])
def test_frozen_family_rules(family, params, long_rule, short_rule):
    assert strategy_exit(family, params, 0) == long_rule
    assert strategy_exit(family, params, 1) == short_rule


def test_volume_is_a_level_condition_and_long_only():
    assert strategy_exit('volume', {'exit_ma_window': 20}, 0) == 'close below exit MA(20)'
    assert 'unavailable' in strategy_exit('volume', {'exit_ma_window': 20}, 1)


def test_missing_params_are_explicit():
    assert 'unavailable' in strategy_exit('rsi', {}, 0)
    assert 'unavailable' in strategy_exit('unknown', {}, 0)


@pytest.mark.parametrize('direction,delta,level', [(0, .5, '≤ $95.00'), (1, -.5, '≥ $105.00')])
def test_stop_and_delta_estimate_both_directions(direction, delta, level):
    quote = dict(bid=9, ask=11, delta=delta, ts=NOW.isoformat())
    text = format_exit_line('rsi', RSI, direction, 'XYZ', 100, quote, now=NOW)
    assert level in text
    assert 'delta-only ≈ $7.50 (-25% vs quote mid' in text
    assert 'opposite entry may reverse' in text
    assert 'take-profit' not in text


@pytest.mark.parametrize('bad', [dict(delta=None), dict(delta=-.5), dict(delta=float('nan')), dict(bid=0), dict(ask=1), dict(ts='2026-09-09T17:00:00+00:00'), dict(ts='2026-09-09T19:00:00+00:00'), dict(ts='broken')])
def test_bad_or_stale_quote_omits_estimate_but_keeps_rule(bad):
    quote = dict(bid=9, ask=11, delta=.5, ts=NOW.isoformat()) | bad
    text = format_exit_line('rsi', RSI, 0, 'XYZ', 100, quote, now=NOW)
    assert 'delta-only' not in text
    assert '≤ $95.00' in text


def test_configuration_controls_stop_not_hardcoded():
    cfg = dict(USE_STOP_LOSS=True, STOP_LOSS_PERCENT=.02)
    assert '$98.00' in format_exit_line('rsi', RSI, 0, 'XYZ', 100, sim_config=cfg)
    cfg['USE_STOP_LOSS'] = False
    assert 'underlying stop' not in format_exit_line('rsi', RSI, 0, 'XYZ', 100, sim_config=cfg)
    cfg['ATR_SL_WINDOW'] = 14
    text = format_exit_line('rsi', RSI, 0, 'XYZ', 100, sim_config=cfg)
    assert 'dynamic underlying stop' in text and '$98' not in text


def test_both_alert_formatters_include_shared_exit():
    from nn_meta.live.scanner import Signal, format_alert
    from nn_meta.live.v4_scan import format_v4_alert
    from nn_meta.v4_loader import V4Bundle
    sig = Signal('XYZ', 'rsi', 0, 'C', pd.Timestamp('2026-09-09 15:00'), 30, 100, 'rsi', params=RSI)
    row = SimpleNamespace(symbol='XYZ', strategy='rsi', dte=30, entry_ts=sig.bar_ts, score=.7)
    bundle = V4Bundle(family='gbt', mode='filter', threshold=.55, features=[], eligible=True, members=[], config={})
    fresh = dict(direction=0, param_label='rsi', spot=100, params=RSI)
    for msg in (format_alert(sig)[1], format_v4_alert(row, fresh, bundle, True)[1]):
        assert '\nexit: RSI(14) crosses below 70' in msg
        assert 'XYZ ≤ $95.00' in msg
        assert msg.index('\nexit:') < msg.index('\nbar:')


def test_detection_carries_raw_params_without_changing_features(monkeypatch):
    from nn_meta.live import scanner, v4_scan
    bars = pd.DataFrame({'Close': [100.] * 40}, index=pd.date_range('2026-09-09', periods=40, freq='15min'))
    trades = lambda *a, **kw: [(bars.index[-1], bars.index[-1], 0)]
    monkeypatch.setattr(scanner, 'propose_trades', trades)
    monkeypatch.setattr(v4_scan, 'propose_trades', trades)
    spec = dict(best_strategy='rsi', strategies={'rsi': dict(params=RSI, dte=30, param_label='frozen')})
    signal = scanner.detect_fresh_signal('XYZ', bars, spec)
    fresh = v4_scan.fresh_proposals('XYZ', bars, spec, ['rsi'])
    assert signal.params == fresh[0]['params'] == RSI
    assert signal.params is not RSI and fresh[0]['params'] is not RSI
    assert 'params' not in v4_scan.candidate_frame(fresh).columns
