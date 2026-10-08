# nn_meta/v8_signals.py — V8 stage-1 strategy variants (long only).
"""Variant registry and vectorized long entry/exit signals for one symbol's
bars (adjusted OHLCV, columns Open/High/Low/Close/Volume, no gaps).

Catalog families reuse nn_meta.proposals.sweep_signals with the registered
grids (nn_meta.multitimeframe_catalog legacy families). TradingView-source
families are excluded (see docs/specs/V8_STAGE1_PREREG_20261008.json).

New volume families (pre-registered grids below):
  obv_trend     OBV crosses above its EMA(m) → entry; below → exit;
                optional price confirmation close > SMA(close, m)
  vwap_reclaim  close crosses above the rolling n-bar VWAP → entry (optional
                relative-volume filter volume >= k x SMA(volume, n)); close
                crosses below → exit
  adl_breakout  accumulation/distribution line makes a new n-bar high → entry;
                ADL crosses below its SMA(m) → exit
  mfi           Money Flow Index(w) crosses above `lo` → entry; crosses above
                `hi` → exit
"""
from __future__ import annotations

import json
from hashlib import sha256
from itertools import product

import numpy as np
import pandas as pd

from nn_meta.multitimeframe_catalog import PARAMETERS, parameter_variants

CATALOG_FAMILIES = ("ma", "rsi", "macd", "bbands", "stoch", "volume", "elliott",
                    "supertrend", "tv_rating", "squeeze", "keltner", "bbw_squeeze")
NEW_GRIDS = {
    "obv_trend": {"m": [10, 20, 30, 50, 100], "confirm": [0, 1]},
    "vwap_reclaim": {"n": [5, 10, 20, 50], "k": [0.0, 1.5]},
    "adl_breakout": {"n": [20, 50], "m": [10, 20, 50]},
    "mfi": {"w": [7, 14, 21], "lo": [20, 30], "hi": [70, 80]},
}
TIMEFRAMES = ("1h", "1d")


def _canon(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def registry() -> list[dict]:
    """Every stage-1 variant (family, params) for one timeframe."""
    from nn_meta import config
    # parameter_variants requires the full legacy key set (ma + PARAMETERS);
    # TV-source grids are not passed, and only catalog families are kept.
    legacy = {k: config.SWEEP_GRIDS[k] for k in ("ma", *PARAMETERS)}
    out = [{"family": s, "params": p} for s, p in parameter_variants(legacy, {})
           if s in CATALOG_FAMILIES]
    for fam, grid in NEW_GRIDS.items():
        keys = sorted(grid)
        for values in product(*(grid[k] for k in keys)):
            out.append({"family": fam, "params": dict(zip(keys, values))})
    return out


def variants_for(timeframe: str) -> list[dict]:
    out = []
    for v in registry():
        ident = {"family": v["family"], "timeframe": timeframe, "params": v["params"]}
        out.append({**ident, "variant_id": sha256(_canon(ident).encode()).hexdigest()[:16]})
    return out


# ── new volume families ──────────────────────────────────────────────────────

def _cross_above(a: pd.Series, b) -> pd.Series:
    return (a > b) & (a.shift(1) <= (b.shift(1) if isinstance(b, pd.Series) else b))


def _cross_below(a: pd.Series, b) -> pd.Series:
    return (a < b) & (a.shift(1) >= (b.shift(1) if isinstance(b, pd.Series) else b))


def new_family_signals(fam: str, bars: pd.DataFrame, p: dict) -> tuple[pd.Series, pd.Series]:
    c, h, lo, v = bars["Close"], bars["High"], bars["Low"], bars["Volume"]
    if fam == "obv_trend":
        obv = (np.sign(c.diff()).fillna(0) * v).cumsum()
        ema = obv.ewm(span=p["m"], adjust=False, min_periods=p["m"]).mean()
        e, x = _cross_above(obv, ema), _cross_below(obv, ema)
        if p["confirm"]:
            e = e & (c > c.rolling(p["m"]).mean())
    elif fam == "vwap_reclaim":
        tp = (h + lo + c) / 3
        vwap = (tp * v).rolling(p["n"]).sum() / v.rolling(p["n"]).sum()
        e, x = _cross_above(c, vwap), _cross_below(c, vwap)
        if p["k"] > 0:
            e = e & (v >= p["k"] * v.rolling(p["n"]).mean())
    elif fam == "adl_breakout":
        rng = (h - lo).replace(0, np.nan)
        clv = (((c - lo) - (h - c)) / rng).fillna(0)
        adl = (clv * v).cumsum()
        prior_high = adl.rolling(p["n"]).max().shift(1)
        e = (adl > prior_high) & (adl.shift(1) <= prior_high.shift(1))
        x = _cross_below(adl, adl.rolling(p["m"]).mean())
    elif fam == "mfi":
        tp = (h + lo + c) / 3
        mf = tp * v
        up = mf.where(tp > tp.shift(1), 0.0).rolling(p["w"]).sum()
        dn = mf.where(tp < tp.shift(1), 0.0).rolling(p["w"]).sum()
        mfi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
        e, x = _cross_above(mfi, p["lo"]), _cross_above(mfi, p["hi"])
    else:
        raise ValueError(f"unknown family {fam}")
    return e.fillna(False).to_numpy(bool), x.fillna(False).to_numpy(bool)


# ── all variants for one symbol ──────────────────────────────────────────────

def _key(params: dict) -> tuple:
    return tuple(sorted((k, round(float(v), 9)) for k, v in params.items()))


def symbol_signals(bars: pd.DataFrame, variants: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """(entries, exits) as bool arrays of shape (len(variants), len(bars))."""
    from nn_meta.proposals import sweep_signals
    n, T = len(variants), len(bars)
    E = np.zeros((n, T), bool)
    X = np.zeros((n, T), bool)
    by_family: dict[str, list[int]] = {}
    for i, v in enumerate(variants):
        by_family.setdefault(v["family"], []).append(i)
    for fam, idx in by_family.items():
        if fam in NEW_GRIDS:
            for i in idx:
                E[i], X[i] = new_family_signals(fam, bars, variants[i]["params"])
            continue
        frames = sweep_signals(fam, bars)
        ent, ext = frames[0], frames[1]
        names = [nm or f"p{j}" for j, nm in enumerate(ent.columns.names)]
        col_of = {}
        for j, col in enumerate(ent.columns):
            vals = col if isinstance(col, tuple) else (col,)
            col_of[_key(dict(zip(names, vals)))] = j
        ev, xv = ent.to_numpy(bool), ext.to_numpy(bool)
        for i in idx:
            j = col_of[_key(variants[i]["params"])]
            E[i], X[i] = ev[:, j], xv[:, j]
    return E, X
