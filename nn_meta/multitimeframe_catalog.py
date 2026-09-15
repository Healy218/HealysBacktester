"""Enumerate the proposed research universe without selecting winners or launching work.

This is a planning inventory, not a sealed signal/execution dataset. In particular,
declaring a timeframe does not establish that a strategy supports that timeframe.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from itertools import combinations, product
import json

import numpy as np

TIMEFRAMES = (1, 5, 15, 30)
SCHEMA = "multitimeframe-catalog-draft-v1"
PARAMETERS = {
    "rsi": ("rsi_window", "entry_threshold", "exit_threshold"),
    "macd": ("macd_fast_window", "macd_slow_window", "macd_signal_window"),
    "bbands": ("bb_window", "bb_alpha"),
    "stoch": ("stoch_k_window", "stoch_d_window", "oversold", "overbought"),
    "volume": ("volume_window", "volume_multiplier", "exit_ma_window"),
    "elliott": ("swing_order", "fib_level", "fib_tolerance"),
    "supertrend": ("st_window", "st_mult"),
    "keltner": ("kc_window", "kc_mult"),
    "bbw_squeeze": ("bbw_window", "bbw_lookback"),
    "tv_rating": ("entry_rating", "exit_rating"),
    "squeeze": ("sq_bb_mult", "sq_kc_mult"),
}
GRID_KEYS = {
    "rsi": ("window", "entry", "exit"),
    "macd": ("fast", "slow", "signal"),
    "bbands": ("window", "std"),
    "stoch": ("k", "d", "oversold", "overbought"),
    "volume": ("vol_window", "vol_mult", "exit_ma"),
    "elliott": ("swing", "fib", "tol"),
    "supertrend": ("window", "mult"),
    "keltner": ("window", "mult"),
    "bbw_squeeze": ("window", "lookback"),
    "tv_rating": ("entry", "exit"),
    "squeeze": ("bb_mult", "kc_mult"),
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _scalar(value):
    return value.item() if isinstance(value, np.generic) else value


def parameter_variants(legacy_grids, source_grids):
    """Match registered arange/exclusive-stop semantics and fast < slow guards."""
    expected = {"ma", *PARAMETERS}
    if set(legacy_grids) != expected or expected.intersection(source_grids):
        raise ValueError("Unrecognized or overlapping registry; update the catalog adapter")
    for strategy in sorted(legacy_grids):
        grid = legacy_grids[strategy]
        if strategy == "ma":
            if set(grid) != {"windows"}:
                raise ValueError("Unrecognized MA grid")
            for fast, slow in combinations(np.arange(*grid["windows"]), 2):
                yield strategy, {"fast_window": _scalar(fast), "slow_window": _scalar(slow)}
            continue
        keys, names = GRID_KEYS[strategy], PARAMETERS[strategy]
        if set(grid) != set(keys):
            raise ValueError(f"Unrecognized grid keys for {strategy}")
        for values in product(*(np.arange(*grid[key]) for key in keys)):
            if strategy == "macd" and values[0] >= values[1]:
                continue
            yield strategy, dict(zip(names, map(_scalar, values)))
    # Source publication defaults are explicit values, NOT arange specifications.
    for strategy in sorted(source_grids):
        grid = source_grids[strategy]
        keys = sorted(grid)
        for values in product(*(grid[key] for key in keys)):
            yield strategy, dict(zip(keys, map(_scalar, values)))


def build_catalog(symbols, legacy_grids, source_grids, *, timeframes=TIMEFRAMES):
    symbols, timeframes = list(symbols), list(timeframes)
    if not symbols or any(not isinstance(s, str) or not s.strip() for s in symbols):
        raise ValueError("Expected a nonempty symbol inventory")
    if len(set(symbols)) != len(symbols):
        raise ValueError("Duplicate symbols")
    if (not timeframes or len(set(timeframes)) != len(timeframes)
            or any(type(tf) is not int or tf not in TIMEFRAMES for tf in timeframes)):
        raise ValueError("Timeframes must be unique members of 1/5/15/30")
    variants = list(parameter_variants(legacy_grids, source_grids))
    records = []
    for timeframe in sorted(timeframes):
        for strategy, params in variants:
            identity = {"strategy": strategy, "signal_minutes": timeframe, "params": params}
            records.append({**identity, "variant_id": sha256(canonical(identity).encode()).hexdigest()})
    if len({r["variant_id"] for r in records}) != len(records):
        raise ValueError("Duplicate parameter variants")
    payload = {
        "schema": SCHEMA, "status": "planning_only", "ready_for_build": False,
        "symbols": sorted(symbols), "signal_minutes": sorted(timeframes),
        "option_execution_minutes": 1,
        "families": dict(sorted(Counter(s for s, _ in variants).items())),
        "parameter_variants_per_timeframe": len(variants),
        "variants_per_symbol": len(records),
        "symbol_timeframe_parameter_combinations": len(symbols) * len(records),
        "records": records,
        "count_excludes": ["direction", "DTE target", "contract", "signal event", "model trial"],
        "requires_validation": ["minute stock coverage", "per-timeframe strategy semantics",
            "bounded vectorization and sweep/single parity", "complete frozen execution quotes",
            "causal feature/execution engine", "purged evaluation", "full-pipeline resource pilot"],
    }
    return {**payload, "catalog_sha256": sha256(canonical(payload).encode()).hexdigest()}


def registered_catalog(symbols):
    from nn_meta import config
    from nn_meta.tradingview_proposals import SWEEP_GRIDS as source_grids

    legacy = {k: v for k, v in config.SWEEP_GRIDS.items() if k not in source_grids}
    return build_catalog(symbols, legacy, source_grids)
