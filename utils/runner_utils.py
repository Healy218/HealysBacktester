# utils/runner_utils.py
"""
Shared helpers for the backtests/run_*.py strategy runners.

Every runner used to carry verbatim copies of the stop-loss / take-profit
resolvers, the Portfolio.from_signals kwargs builder, the parameter-range
builders, and the error-result factory. They now live here so a config key
added in one place propagates to all runners.
"""

import numpy as np


def sl_stop(cfg):
    """Resolve the stop-loss fraction, or None when disabled/unset."""
    pct = cfg.get("STOP_LOSS_PERCENT")
    return pct if cfg.get("USE_STOP_LOSS") and pct else None


def tp_stop(cfg):
    """Resolve the take-profit fraction, or None when disabled/unset."""
    pct = cfg.get("TAKE_PROFIT_PERCENT")
    return pct if cfg.get("USE_TAKE_PROFIT") and pct else None


def sim_kwargs(cfg, sl=None, tp=None):
    """
    Build the kwargs dict consumed by the chunked simulator / Portfolio.from_signals.

    sl/tp may be passed pre-resolved (the common case); when omitted they are
    derived from cfg via sl_stop()/tp_stop().
    """
    if sl is None:
        sl = sl_stop(cfg)
    if tp is None:
        tp = tp_stop(cfg)
    return dict(
        initial_capital=cfg.get("INITIAL_CAPITAL", 100_000.0),
        fees=cfg.get("FEES_PERCENT", 0.001),
        slippage=cfg.get("SLIPPAGE_PERCENT", 0.0005),
        size=cfg.get("DEFAULT_SIZE", 0.9),
        size_type=cfg.get("DEFAULT_SIZE_TYPE", "percent"),
        sl_stop=sl,
        tp_stop=tp,
        trend_filter_window=cfg.get("TREND_FILTER_WINDOW", 0),
        atr_sl_window=cfg.get("ATR_SL_WINDOW"),
        atr_sl_multiplier=cfg.get("ATR_SL_MULTIPLIER", 2.0),
        use_trailing_stop=cfg.get("USE_TRAILING_STOP", False),
        atr_position_sizing=cfg.get("ATR_POSITION_SIZING", False),
        risk_per_trade=cfg.get("RISK_PER_TRADE", 0.01),
    )


def arange_int(cfg, start_key, end_key, step_key, default):
    """Integer np.arange from cfg keys, falling back to a (start, end, step) default."""
    s, e, st = default
    return np.arange(
        cfg.get(start_key, s), cfg.get(end_key, e), cfg.get(step_key, st), dtype=int
    )


def linspace(cfg, start_key, end_key, step_key, default):
    """Float np.linspace from cfg keys, inclusive of the endpoint."""
    s, e, st = default
    start = cfg.get(start_key, s)
    end = cfg.get(end_key, e)
    step = cfg.get(step_key, st)
    n = max(1, int(round((end - start) / step)) + 1)
    return np.linspace(start, end, n)


def err(msg, tag, logger):
    """Log a warning and return the standard empty-result dict shared by all runners."""
    logger.warning(f"[{tag}] {msg}")
    return {"top5": [], "error": msg, "portfolio": None, "price_data": None}
