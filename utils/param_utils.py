# utils/param_utils.py
"""
Shared helpers for ranking parameter combinations and formatting their labels.
Used by all backtest runner modules in backtests/.
"""

import gc
import numpy as np
import pandas as pd
from typing import Any, Tuple
from utils.logging_utils import setup_logging

logger = setup_logging(log_file="logs/backtester.log")

# How many columns to process at a time when extracting metrics.
# Keeps peak memory bounded: 50k columns × ~250 bars ≈ 100 MB per metric.
_CHUNK_SIZE = 50_000


def top5_from_portfolio(portfolio, n: int = 5) -> list[dict]:
    """
    Returns the best parameter combination for each of three metrics:
      - Best Sharpe Ratio
      - Best Total Return %
      - Best Win Rate %

    For large portfolios (>50k columns), metrics are extracted in chunks to
    avoid OOM kills.  Each chunk's best is tracked, then the overall best
    is selected from the chunk winners.

    Args:
        portfolio: A multi-column vectorbt Portfolio object.
        n: Unused, kept for API compatibility.

    Returns:
        List of up to 3 dicts (one per metric), each describing the best
        combination for that metric.  Returns [] if metrics cannot be computed.
    """
    try:
        columns = portfolio.wrapper.columns
        n_cols = len(columns)

        if n_cols <= _CHUNK_SIZE:
            return _rank_portfolio(portfolio)

        # --- Chunked processing for large portfolios ---
        logger.info(
            f"Large portfolio ({n_cols:,} columns): processing in chunks of {_CHUNK_SIZE:,}"
        )

        # Track the best candidate per metric across all chunks
        best_sharpe = {"val": -np.inf, "col_idx": None}
        best_return = {"val": -np.inf, "col_idx": None}
        best_winrate = {"val": -np.inf, "col_idx": None}

        for start in range(0, n_cols, _CHUNK_SIZE):
            end = min(start + _CHUNK_SIZE, n_cols)
            chunk_cols = columns[start:end]
            logger.info(f"  Chunk {start:,}–{end:,} ({len(chunk_cols):,} columns)...")

            try:
                chunk_pf = portfolio[list(chunk_cols)]

                ret = chunk_pf.total_return()
                sharpe = chunk_pf.sharpe_ratio().replace([np.inf, -np.inf], np.nan)

                # Mask blown-up combos
                blown_up = ret <= -0.95
                sharpe = sharpe.where(~blown_up, np.nan)
                ret = ret.where(~blown_up, np.nan)

                # Trade count filter
                try:
                    trade_count = chunk_pf.trades.count()
                except Exception:
                    trade_count = pd.Series(0, index=chunk_cols)

                too_few = trade_count < 3
                sharpe = sharpe.where(~too_few, np.nan)
                ret = ret.where(~too_few, np.nan)

                # Win rate
                try:
                    win_rate = chunk_pf.trades.win_rate()
                except Exception:
                    win_rate = pd.Series(np.nan, index=chunk_cols)
                win_rate = win_rate.where(~blown_up & ~too_few, np.nan)

                # Track best per metric (use global column index)
                if sharpe.notna().any():
                    s_best = sharpe.idxmax(skipna=True)
                    if s_best is not None and not np.isnan(sharpe[s_best]):
                        if sharpe[s_best] > best_sharpe["val"]:
                            best_sharpe["val"] = sharpe[s_best]
                            best_sharpe["col_idx"] = columns.get_loc(s_best)

                if ret.notna().any():
                    r_best = ret.idxmax(skipna=True)
                    if r_best is not None and not np.isnan(ret[r_best]):
                        if ret[r_best] > best_return["val"]:
                            best_return["val"] = ret[r_best]
                            best_return["col_idx"] = columns.get_loc(r_best)

                if win_rate.notna().any():
                    w_best = win_rate.idxmax(skipna=True)
                    if w_best is not None and not np.isnan(win_rate[w_best]):
                        if win_rate[w_best] > best_winrate["val"]:
                            best_winrate["val"] = win_rate[w_best]
                            best_winrate["col_idx"] = columns.get_loc(w_best)

                # Free chunk memory
                del chunk_pf, ret, sharpe, trade_count, win_rate, blown_up, too_few
                gc.collect()

            except Exception as e:
                logger.warning(f"  Chunk {start}–{end} failed: {e}")
                continue

        # Build results from the winners
        results = []
        for label, best in [
            ("Best Sharpe", best_sharpe),
            ("Best Return", best_return),
            ("Best Win Rate", best_winrate),
        ]:
            if best["col_idx"] is not None:
                results.append(_make_row_from_index(portfolio, best["col_idx"], label))

        return results

    except Exception as e:
        logger.error(f"Error computing best-by-metric results: {e}")
        return []


def _rank_portfolio(portfolio) -> list[dict]:
    """Non-chunked ranking for portfolios that fit in memory."""
    sharpe = portfolio.sharpe_ratio().replace([np.inf, -np.inf], np.nan)
    ret = portfolio.total_return()
    drawdown = portfolio.max_drawdown()

    blown_up = ret <= -0.95
    if blown_up.any():
        n_blown = int(blown_up.sum())
        logger.info(f"Excluding {n_blown} blown-up parameter combinations (return <= -95%) from ranking.")
        sharpe = sharpe.where(~blown_up, np.nan)
        ret = ret.where(~blown_up, np.nan)

    try:
        win_rate = portfolio.trades.win_rate()
    except Exception:
        win_rate = pd.Series(np.nan, index=portfolio.wrapper.columns)
    win_rate = win_rate.where(~blown_up, np.nan)

    try:
        trade_count = portfolio.trades.count()
    except Exception:
        trade_count = pd.Series(0, index=portfolio.wrapper.columns)

    MIN_TRADES = 3
    too_few = trade_count < MIN_TRADES
    if too_few.any():
        n_few = int(too_few.sum())
        logger.info(f"Excluding {n_few} combos with < {MIN_TRADES} trades from ranking.")
        sharpe = sharpe.where(~too_few, np.nan)
        ret = ret.where(~too_few, np.nan)
        win_rate = win_rate.where(~too_few, np.nan)

    try:
        best_trade = portfolio.trades.returns.max() * 100
    except Exception:
        best_trade = pd.Series(np.nan, index=portfolio.wrapper.columns)

    def _make_row(col, ranked_by: str) -> dict:
        col_int_idx = portfolio.wrapper.columns.get_loc(col)
        return {
            "ranked_by":             ranked_by,
            "portfolio_col_int_idx": int(col_int_idx),
            "param_label":           _format_col_label(col, portfolio.wrapper.columns),
            "total_return_pct":      _safe_float(ret.get(col, np.nan) * 100),
            "sharpe_ratio":          _safe_float(sharpe.get(col, np.nan)),
            "max_drawdown_pct":      _safe_float(abs(drawdown.get(col, np.nan)) * 100),
            "win_rate_pct":          _safe_float(win_rate.get(col, np.nan) * 100),
            "best_trade_pct":        _safe_float(best_trade.get(col, np.nan)),
            "total_trades":          int(trade_count.get(col, 0)),
        }

    results = []

    if sharpe.notna().any():
        best_sharpe_col = sharpe.idxmax(skipna=True)
        if best_sharpe_col is not None:
            results.append(_make_row(best_sharpe_col, "Best Sharpe"))

    if ret.notna().any():
        best_ret_col = ret.idxmax(skipna=True)
        if best_ret_col is not None:
            results.append(_make_row(best_ret_col, "Best Return"))

    if win_rate.notna().any():
        best_wr_col = win_rate.idxmax(skipna=True)
        if best_wr_col is not None:
            results.append(_make_row(best_wr_col, "Best Win Rate"))

    return results


def _make_row_from_index(portfolio, col_int_idx: int, ranked_by: str) -> dict:
    """
    Builds a result row by extracting stats for a single column.
    Used by the chunked path to avoid re-materializing the full portfolio.
    """
    col = portfolio.wrapper.columns[col_int_idx]
    single_pf = portfolio[col]

    try:
        ret_val = float(single_pf.total_return())
    except Exception:
        ret_val = np.nan
    try:
        sharpe_val = float(single_pf.sharpe_ratio())
    except Exception:
        sharpe_val = np.nan
    try:
        dd_val = float(single_pf.max_drawdown())
    except Exception:
        dd_val = np.nan
    try:
        wr_val = float(single_pf.trades.win_rate())
    except Exception:
        wr_val = np.nan
    try:
        bt_val = float(single_pf.trades.returns.max() * 100)
    except Exception:
        bt_val = np.nan
    try:
        tc_val = int(single_pf.trades.count())
    except Exception:
        tc_val = 0

    return {
        "ranked_by":             ranked_by,
        "portfolio_col_int_idx": int(col_int_idx),
        "param_label":           _format_col_label(col, portfolio.wrapper.columns),
        "total_return_pct":      _safe_float(ret_val * 100),
        "sharpe_ratio":          _safe_float(sharpe_val),
        "max_drawdown_pct":      _safe_float(abs(dd_val) * 100),
        "win_rate_pct":          _safe_float(wr_val * 100),
        "best_trade_pct":        _safe_float(bt_val),
        "total_trades":          tc_val,
    }


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
    """
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
    """
    if not name:
        return "param"
    n = name
    for prefix in ("macd_", "ma_", "rsi_", "vbt_", "bb_", "bbands_", "stoch_"):
        if n.startswith(prefix):
            n = n[len(prefix):]
            break
    for suffix in ("_window", "_threshold"):
        if n.endswith(suffix):
            n = n[: -len(suffix)]
            break
    return n or name
