# nn_meta/proposals.py
"""Proposal-engine registry: every offline-backtestable built-in strategy.

Two entry points per strategy, both returning the standard 4-tuple
(entries, exits, short_entries, short_exits):

  sweep_signals(strategy, bars)          — full (coarse) parameter sweep for
                                           the baseline freeze
  single_signals(strategy, bars, params) — one frozen parameter set for
                                           replay/evaluation

``params_from_portfolio(pf, col_int_idx)`` recovers the winning parameter
dict straight from the portfolio's MultiIndex column (level names → values),
avoiding any param-label string parsing.

Sentiment is intentionally absent (live news feed, not offline-backtestable).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from signals import (bbands_breakout, elliott_wave_signals, ma_crossover,
                     macd_signals, rsi_threshold, stoch_crossover,
                     tv_signals, volume_breakout)
from nn_meta import config


def _arange(spec: tuple, dtype=None) -> np.ndarray:
    a = np.arange(*spec)
    return a.astype(dtype) if dtype else a


def params_from_portfolio(pf, col_int_idx: int) -> dict:
    """Winning column's MultiIndex (names → values) as a plain params dict."""
    cols = pf.wrapper.columns
    col = cols[col_int_idx]
    if not isinstance(col, tuple):
        col = (col,)
    names = [n or f"p{i}" for i, n in enumerate(cols.names)]
    out = {}
    for name, val in zip(names, col):
        v = float(val)
        out[name] = int(v) if v == int(v) else v
    return out


# ── sweep signal builders ─────────────────────────────────────────────────────

def sweep_signals(strategy: str, bars: pd.DataFrame):
    g = config.SWEEP_GRIDS[strategy]
    close = bars["Close"]
    short = config.ENABLE_SHORTING

    if strategy == "ma":
        return ma_crossover.generate_ma_signals(
            close, _arange(g["windows"], int), enable_shorting=short)
    if strategy == "rsi":
        return rsi_threshold.generate_rsi_signals(
            close, _arange(g["window"], int), _arange(g["entry"]),
            _arange(g["exit"]), enable_shorting=short)
    if strategy == "macd":
        return macd_signals.generate_macd_signals(
            close, _arange(g["fast"], int), _arange(g["slow"], int),
            _arange(g["signal"], int), short_entries=short, short_exits=short)
    if strategy == "bbands":
        return bbands_breakout.generate_bbands_signals(
            close, _arange(g["window"], int), _arange(g["std"]),
            enable_shorting=short)
    if strategy == "stoch":
        return stoch_crossover.generate_stoch_signals(
            bars["High"], bars["Low"], close,
            _arange(g["k"], int), _arange(g["d"], int),
            oversold_range=_arange(g["oversold"], int),
            overbought_range=_arange(g["overbought"], int),
            enable_shorting=short)
    if strategy == "volume":
        return volume_breakout.generate_volume_signals(
            ohlcv_df=bars,
            volume_window_range=_arange(g["vol_window"], int),
            volume_multiplier_range=_arange(g["vol_mult"]),
            exit_ma_window_range=_arange(g["exit_ma"], int))
    if strategy == "elliott":
        return elliott_wave_signals.generate_elliott_wave_signals(
            bars["High"], bars["Low"], close,
            _arange(g["swing"], int), _arange(g["fib"]), _arange(g["tol"]),
            enable_shorting=short)
    if strategy == "supertrend":
        return tv_signals.generate_supertrend_signals(
            bars, _arange(g["window"], int), _arange(g["mult"]),
            enable_shorting=short)
    if strategy == "tv_rating":
        return tv_signals.generate_tv_rating_signals(
            bars, _arange(g["entry"]), _arange(g["exit"]),
            enable_shorting=short)
    if strategy == "squeeze":
        return tv_signals.generate_squeeze_signals(
            bars, _arange(g["bb_mult"]), _arange(g["kc_mult"]),
            enable_shorting=short)
    raise ValueError(f"unknown proposal strategy: {strategy}")


# ── single frozen-parameter builders ─────────────────────────────────────────
# Length-1 parameter arrays squeeze MultiIndex levels inside several shared
# generators (same family of bug as MA's run_combs Series squeeze). Fix
# WITHOUT touching dashboard signal code: pad ONE parameter with a dummy
# value so the generator emits >= 2 proper columns, then select the frozen
# column exactly. Replay therefore stays sweep-identical by construction.

def _one(v, dtype=float) -> np.ndarray:
    return np.array([dtype(v)])


def _pad(v, dtype=float) -> np.ndarray:
    step = 1 if dtype is int else 0.5
    return np.array([dtype(v), dtype(v) + step])


def _select_col(frames: tuple, params: dict):
    """Slice the single column whose level values match ``params`` exactly."""
    ent = frames[0]
    names = [n or f"p{i}" for i, n in enumerate(ent.columns.names)]
    for col in ent.columns:
        vals = col if isinstance(col, tuple) else (col,)
        if all(abs(float(v) - float(params[n])) < 1e-9
               for n, v in zip(names, vals)):
            return tuple(df[[col]] if df is not None else None for df in frames)
    raise KeyError(f"frozen column {params} not found in generator output "
                   f"(columns: {list(ent.columns)[:4]}…)")


def single_signals(strategy: str, bars: pd.DataFrame, params: dict):
    close = bars["Close"]
    short = config.ENABLE_SHORTING
    p = params

    if strategy == "ma":
        fast, slow = int(p["fast_window"]), int(p["slow_window"])
        dummy = slow + 1 if slow + 1 != fast else slow + 2
        windows = np.array(sorted({fast, slow, dummy}))
        frames = ma_crossover.generate_ma_signals(
            close, windows, enable_shorting=short)
    elif strategy == "rsi":
        frames = rsi_threshold.generate_rsi_signals(
            close, _pad(p["rsi_window"], int), _one(p["entry_threshold"]),
            _one(p["exit_threshold"]), enable_shorting=short)
    elif strategy == "macd":
        frames = macd_signals.generate_macd_signals(
            close, _one(p["macd_fast_window"], int),
            _one(p["macd_slow_window"], int),
            _pad(p["macd_signal_window"], int),
            short_entries=short, short_exits=short)
    elif strategy == "bbands":
        # level names are bb_window / bb_alpha (not bbands_*)
        frames = bbands_breakout.generate_bbands_signals(
            close, _one(p["bb_window"], int), _pad(p["bb_alpha"]),
            enable_shorting=short)
    elif strategy == "stoch":
        frames = stoch_crossover.generate_stoch_signals(
            bars["High"], bars["Low"], close,
            _one(p["stoch_k_window"], int), _pad(p["stoch_d_window"], int),
            oversold_range=_one(p["oversold"], int),
            overbought_range=_one(p["overbought"], int),
            enable_shorting=short)
    elif strategy == "volume":
        # single-value volume_window AND exit_ma_window each squeeze an
        # internal frame to 1-D — pad both (4 combos, frozen one selected)
        frames = volume_breakout.generate_volume_signals(
            ohlcv_df=bars,
            volume_window_range=_pad(p["volume_window"], int),
            volume_multiplier_range=_one(p["volume_multiplier"]),
            exit_ma_window_range=_pad(p["exit_ma_window"], int))
    elif strategy == "elliott":
        frames = elliott_wave_signals.generate_elliott_wave_signals(
            bars["High"], bars["Low"], close,
            _one(p["swing_order"], int), _one(p["fib_level"]),
            _pad(p["fib_tolerance"]), enable_shorting=short)
    elif strategy == "supertrend":
        # tv_signals generators build columns explicitly — no squeeze, no pad
        frames = tv_signals.generate_supertrend_signals(
            bars, _one(p["st_window"], int), _one(p["st_mult"]),
            enable_shorting=short)
    elif strategy == "tv_rating":
        frames = tv_signals.generate_tv_rating_signals(
            bars, _one(p["entry_rating"]), _one(p["exit_rating"]),
            enable_shorting=short)
    elif strategy == "squeeze":
        frames = tv_signals.generate_squeeze_signals(
            bars, _one(p["sq_bb_mult"]), _one(p["sq_kc_mult"]),
            enable_shorting=short)
    else:
        raise ValueError(f"unknown proposal strategy: {strategy}")
    return _select_col(frames, params)
