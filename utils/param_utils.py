# utils/param_utils.py
"""
Shared helpers for ranking parameter combinations and formatting their labels.
Used by all four backtest runner modules in backtests/.
"""

import numpy as np
import pandas as pd
from typing import Any, Tuple
from utils.logging_utils import setup_logging

logger = setup_logging(log_file="logs/backtester.log")


def top5_from_portfolio(portfolio, n: int = 5) -> list[dict]:
    """
    Ranks all parameter combinations in a multi-column vectorbt Portfolio by
    Sharpe Ratio and returns the top N as a list of dicts.

    Each dict contains only JSON-serializable values so it can be stored in
    a Dash dcc.Store component.  The 'portfolio_col_int_idx' field is an
    integer position into portfolio.wrapper.columns — use it to re-slice the
    portfolio object without any tuple/type-conversion headaches.

    Args:
        portfolio: A multi-column vectorbt Portfolio object.
        n: Number of top combinations to return.

    Returns:
        List of dicts (length <= n), sorted best-first by Sharpe Ratio.
        Returns [] if metrics cannot be computed.
    """
    try:
        # Pull individual metrics — faster than portfolio.stats(agg_func=None)
        # which computes every metric for every combination.
        sharpe   = portfolio.sharpe_ratio().replace([np.inf, -np.inf], np.nan)
        ret      = portfolio.total_return()
        drawdown = portfolio.max_drawdown()

        # Trades-level metrics — wrap in try/except, some combos have 0 trades
        try:
            win_rate = portfolio.trades.win_rate()
        except Exception:
            win_rate = pd.Series(np.nan, index=portfolio.wrapper.columns)

        try:
            trade_count = portfolio.trades.count()
        except Exception:
            trade_count = pd.Series(0, index=portfolio.wrapper.columns)

        # Sort by Sharpe descending, ignoring NaN
        top_cols = sharpe.nlargest(n)

        results = []
        for rank, (col, sharpe_val) in enumerate(top_cols.items(), start=1):
            # Integer position — type-safe way to re-slice later
            col_int_idx = portfolio.wrapper.columns.get_loc(col)

            results.append({
                "rank":                 rank,
                "portfolio_col_int_idx": int(col_int_idx),
                "param_label":          _format_col_label(col, portfolio.wrapper.columns),
                "total_return_pct":     _safe_float(ret.get(col, np.nan) * 100),
                "sharpe_ratio":         _safe_float(sharpe_val),
                "max_drawdown_pct":     _safe_float(abs(drawdown.get(col, np.nan)) * 100),
                "win_rate_pct":         _safe_float(win_rate.get(col, np.nan) * 100),
                "total_trades":         int(trade_count.get(col, 0)),
            })

        return results

    except Exception as e:
        logger.error(f"Error computing top-{n} results: {e}")
        return []


def _safe_float(val) -> float | None:
    """Converts a value to a plain Python float, returning None for NaN/inf."""
    try:
        f = float(val)
        return None if (np.isnan(f) or np.isinf(f)) else round(f, 4)
    except (TypeError, ValueError):
        return None


def _format_col_label(col: Any, columns: pd.Index) -> str:
    """
    Builds a human-readable string from a portfolio column value.

    Handles scalars, plain tuples, and pandas MultiIndex levels — reads the
    actual level names from the index so the labels match the indicator params.

    Examples:
      (112, 137)                         → "fast=112, slow=137"
      (np.int64(5), np.float64(28.0), …) → "rsi_window=5, entry_threshold=28.00, …"
      42                                 → "window=42"
    """
    # Resolve level names from the column index
    if isinstance(columns, pd.MultiIndex):
        names = list(columns.names)
    else:
        names = [columns.name or "param"]

    if not isinstance(col, tuple):
        col = (col,)

    parts = []
    for i, val in enumerate(col):
        name = names[i] if i < len(names) else f"p{i}"
        short_name = _shorten_level_name(name)
        try:
            fval = float(val)
            if fval == int(fval):
                parts.append(f"{short_name}={int(fval)}")
            else:
                parts.append(f"{short_name}={fval:.2f}")
        except (TypeError, ValueError):
            parts.append(f"{short_name}={val}")

    return ", ".join(parts)


def _shorten_level_name(name: str) -> str:
    """
    Converts a raw vectorbt column level name to a short, readable label.

    Examples:
      fast_window      -> fast
      slow_window      -> slow
      macd_fast_window -> fast
      rsi_window       -> rsi
      entry_threshold  -> entry
      exit_threshold   -> exit
    """
    if not name:
        return "param"
    n = name
    # 1. Strip common indicator prefixes  (e.g. "macd_" from "macd_fast_window")
    for prefix in ("macd_", "ma_", "rsi_", "vbt_", "bb_"):
        if n.startswith(prefix):
            n = n[len(prefix):]
            break
    # 2. Strip trailing "_window" or "_threshold"
    for suffix in ("_window", "_threshold"):
        if n.endswith(suffix):
            n = n[: -len(suffix)]
            break
    return n or name  # fall back to original if we accidentally emptied it
