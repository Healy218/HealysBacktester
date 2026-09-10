"""Display the frozen underlying exit policy; never place orders or alter signals."""
from __future__ import annotations

from datetime import datetime, timezone
import math

from nn_meta import config


def strategy_exit(strategy: str, params: dict | None, direction: int) -> str:
    p = params or {}
    short = direction == 1
    cross = "above" if short else "below"
    def n(key):
        value = float(p[key])
        if not math.isfinite(value):
            raise ValueError(key)
        return f"{value:g}"
    try:
        if strategy == "ma":
            return f"MA({n('fast_window')}) crosses {cross} MA({n('slow_window')})"
        if strategy == "rsi":
            threshold = n('entry_threshold' if short else 'exit_threshold')
            return f"RSI({n('rsi_window')}) crosses {cross} {threshold}"
        if strategy == "macd":
            return f"MACD({n('macd_fast_window')},{n('macd_slow_window')}) crosses {cross} signal({n('macd_signal_window')})"
        if strategy == "bbands":
            return f"close crosses {cross} Bollinger middle band({n('bb_window')})"
        if strategy == "stoch":
            bound = n('oversold' if short else 'overbought')
            relation = '<' if short else '>'
            return f"stochastic({n('stoch_k_window')},{n('stoch_d_window')}) %K crosses {cross} %D with %K {relation} {bound}"
        if strategy == "volume" and not short:
            return f"close below exit MA({n('exit_ma_window')})"
        if strategy == "supertrend":
            return f"Supertrend({n('st_window')},{n('st_mult')}) flips {'up' if short else 'down'}"
        if strategy == "tv_rating":
            threshold = float(n('exit_rating')) * (-1 if short else 1)
            return f"technical rating crosses {cross} {threshold:g}"
        if strategy == "squeeze":
            return f"squeeze momentum crosses {cross} zero"
        if strategy == "keltner":
            return f"close crosses {cross} Keltner EMA({n('kc_window')})"
        if strategy == "bbw_squeeze":
            return f"close crosses {cross} Bollinger SMA({n('bbw_window')})"
        if strategy == "elliott":
            regime = 'down' if short else 'up'
            return f"close reaches latest swing high or low in {regime}-swing regime (order {n('swing_order')})"
    except (KeyError, TypeError, ValueError, OverflowError):
        pass
    return "strategy exit signal (rule details unavailable)"


def _option_estimate(quote, spot, stop, direction, now):
    """Local delta approximation, deliberately not a premium stop or fill forecast."""
    try:
        bid, ask, delta = (float(quote[k]) for k in ('bid', 'ask', 'delta'))
        ts = datetime.fromisoformat(quote['ts'].replace('Z', '+00:00'))
        if ts.tzinfo is None:
            return ''
        age = (now - ts).total_seconds()
        if not all(map(math.isfinite, (bid, ask, delta))) or not 0 <= age <= 180:
            return ''
        if not 0 < bid <= ask or not (0 < delta <= 1 if direction == 0 else -1 <= delta < 0):
            return ''
        mid = (bid + ask) / 2
        estimate = max(0, mid + delta * (stop - spot))
        return f", ≈ option ${estimate:.2f}, {estimate / mid - 1:+.0%} (Δ-only)"
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return ''


def format_exit_line(strategy, params, direction, symbol, spot, quote=None, *, sim_config=None, now=None):
    cfg = config.SIM_CONFIG if sim_config is None else sim_config
    parts = [strategy_exit(strategy, params, direction)]
    if cfg.get('ATR_SL_WINDOW') or cfg.get('USE_TRAILING_STOP'):
        parts.append('dynamic stock stop')
    elif cfg.get('USE_STOP_LOSS') and cfg.get('STOP_LOSS_PERCENT'):
        fraction = float(cfg['STOP_LOSS_PERCENT'])
        stop = float(spot) * (1 + fraction if direction == 1 else 1 - fraction)
        if math.isfinite(stop) and spot > 0:
            relation = '≥' if direction == 1 else '≤'
            estimate = _option_estimate(quote, spot, stop, direction, now or datetime.now(timezone.utc))
            move = fraction if direction == 1 else -fraction
            parts.append(f'{symbol} {relation} ${stop:,.2f} ({move:+.0%} stock stop{estimate})')
    if cfg.get('USE_TAKE_PROFIT') and cfg.get('TAKE_PROFIT_PERCENT'):
        fraction = float(cfg['TAKE_PROFIT_PERCENT'])
        target = spot * (1 - fraction if direction == 1 else 1 + fraction)
        parts.append(f'underlying take-profit ${target:,.2f}')
    if cfg.get('ENABLE_SHORTING') and strategy != 'volume':
        parts.append('opposite signal')
    return 'exit: ' + ' · or '.join(parts) + ' · roll at expiry when available'
