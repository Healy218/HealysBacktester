# utils/chunked_runner.py
"""
Chunked simulation and ranking for large parameter sweeps.

When the number of parameter combinations exceeds what can fit in memory
for a single Portfolio.from_signals() call, this module splits the work
into manageable chunks:

  1. Slice signal DataFrames into chunks of N columns
  2. Simulate each chunk independently
  3. Rank each chunk and track the best candidate per metric
  4. Re-simulate just the winning columns for the dashboard

The chunk size is adaptive: it targets ~2 GB of peak memory for vectorbt's
internal float64 arrays, scaling with the number of price bars.
"""

import gc
import pandas as pd
import numpy as np
from utils.logging_utils import setup_logging
from utils.param_utils import top5_from_portfolio
from portfolio import simulator

logger = setup_logging(log_file="logs/backtester.log")

# Memory budget per chunk: ~2 GB for vectorbt internals
_TARGET_CHUNK_BYTES = 2 * 1024**3
# Rough estimate of float64 arrays vectorbt allocates per simulation
_ARRAYS_PER_SIM = 5


def _compute_chunk_size(n_rows: int) -> int:
    """
    Calculates how many columns can be simulated at once without exceeding
    the memory budget.  Clamps to [1_000, 50_000].
    """
    cols = _TARGET_CHUNK_BYTES // (_ARRAYS_PER_SIM * max(n_rows, 1) * 8)
    return max(1_000, min(50_000, int(cols)))


def simulate_and_rank(
    price_data: pd.DataFrame,
    entries: pd.DataFrame,
    exits: pd.DataFrame,
    short_entries: pd.DataFrame | None,
    short_exits: pd.DataFrame | None,
    freq: str,
    sim_kwargs: dict,
    strategy_tag: str = "",
    progress_callback=None,
) -> dict:
    """
    Simulate a parameter sweep and return the top-3 results (best Sharpe,
    best return, best win rate) plus a lightweight portfolio for graphing.

    For small sweeps (≤ chunk_size columns) this is a thin wrapper around
    simulator.run_backtest + top5_from_portfolio.

    For large sweeps it processes chunks independently, tracks winners,
    and re-simulates only the winners at the end.

    Returns:
        dict with keys: top5, error, portfolio, price_data
    """
    n_cols = entries.shape[1] if entries.ndim == 2 else 1
    n_rows = len(entries)
    chunk_size = _compute_chunk_size(n_rows)

    tag = f"[{strategy_tag}]" if strategy_tag else ""

    # ── Small sweep: process all at once ─────────────────────────────────
    if n_cols <= chunk_size:
        logger.info(f"{tag} Single-pass simulation ({n_cols:,} combos, chunk_size={chunk_size:,})")
        portfolio = simulator.run_backtest(
            price_df=price_data,
            entries_series=entries,
            exits_series=exits,
            short_entries_series=short_entries,
            short_exits_series=short_exits,
            frequency=freq,
            **sim_kwargs,
        )
        if portfolio is None:
            return _err("Simulation returned no portfolio.", price_data)

        top5 = top5_from_portfolio(portfolio, n=5)
        return {"top5": top5, "error": None, "portfolio": portfolio, "price_data": price_data}

    # ── Large sweep: chunked simulation ──────────────────────────────────
    n_chunks = (n_cols + chunk_size - 1) // chunk_size
    logger.info(
        f"{tag} Chunked simulation: {n_cols:,} combos → "
        f"{n_chunks} chunks of ≤{chunk_size:,} columns"
    )

    # Track the best candidate per metric across all chunks.
    # Each entry stores the result row dict plus the raw signal values
    # for that single winning column (so we can re-simulate later without
    # needing the full 500k-column signal DataFrames).
    best: dict[str, dict | None] = {
        "Best Sharpe": None,
        "Best Return": None,
        "Best Win Rate": None,
    }

    for chunk_idx, start in enumerate(range(0, n_cols, chunk_size)):
        end = min(start + chunk_size, n_cols)
        logger.info(f"{tag}   Chunk {chunk_idx + 1}/{n_chunks}: columns {start:,}–{end:,}")

        if progress_callback is not None:
            progress_callback(chunk_idx, n_chunks)

        # Slice signal DataFrames (iloc returns a view — low memory)
        c_entries = entries.iloc[:, start:end]
        c_exits = exits.iloc[:, start:end]
        c_se = short_entries.iloc[:, start:end] if short_entries is not None else None
        c_sx = short_exits.iloc[:, start:end] if short_exits is not None else None

        try:
            chunk_pf = simulator.run_backtest(
                price_df=price_data,
                entries_series=c_entries,
                exits_series=c_exits,
                short_entries_series=c_se,
                short_exits_series=c_sx,
                frequency=freq,
                **sim_kwargs,
            )
            if chunk_pf is None:
                logger.warning(f"{tag}   Chunk {chunk_idx + 1} returned no portfolio, skipping.")
                continue

            chunk_top = top5_from_portfolio(chunk_pf, n=5)

            for row in chunk_top:
                metric = row.get("ranked_by", "")
                if metric not in best:
                    continue

                current = best[metric]
                if current is None or _is_better(row, current, metric):
                    # Save the winning column's signal data (tiny: 1 col × n_rows bools)
                    col = chunk_pf.wrapper.columns[row["portfolio_col_int_idx"]]
                    row["_saved_signals"] = _save_col_signals(
                        col, c_entries, c_exits, c_se, c_sx,
                    )
                    best[metric] = row

            del chunk_pf
        except Exception as e:
            logger.warning(f"{tag}   Chunk {chunk_idx + 1} failed: {e}")

        # Free chunk references and collect
        del c_entries, c_exits, c_se, c_sx
        gc.collect()

    # ── Collect winners and re-simulate ──────────────────────────────────
    winners = [(m, info) for m, info in best.items() if info is not None]
    if not winners:
        return _err("No valid results from any chunk.", price_data)

    logger.info(f"{tag} Re-simulating {len(winners)} winning parameter set(s)...")
    if progress_callback is not None:
        progress_callback(n_chunks, n_chunks)  # signal "all chunks done"

    # Deduplicate: if two metrics share the same winning column, simulate once
    seen_cols: dict[tuple | str, int] = {}  # col_label → index in lists
    win_entry_cols = []
    win_exit_cols = []
    win_se_cols = []
    win_sx_cols = []
    col_labels = []

    for _, info in winners:
        saved = info["_saved_signals"]
        col = saved["col_label"]
        col_key = col if not isinstance(col, list) else tuple(col)
        if col_key not in seen_cols:
            idx = len(col_labels)
            seen_cols[col_key] = idx
            col_labels.append(col)
            win_entry_cols.append(saved["entry"])
            win_exit_cols.append(saved["exit"])
            if saved["short_entry"] is not None:
                win_se_cols.append(saved["short_entry"])
            if saved["short_exit"] is not None:
                win_sx_cols.append(saved["short_exit"])

    # Build small signal DataFrames from saved columns
    idx = entries.index
    if len(col_labels) == 1:
        # Single column — use the column label directly
        mi = pd.Index(col_labels)
    else:
        # Multiple columns — try to build a matching MultiIndex
        if isinstance(col_labels[0], tuple):
            mi = pd.MultiIndex.from_tuples(col_labels, names=entries.columns.names)
        else:
            mi = pd.Index(col_labels)

    win_entries_df = pd.DataFrame(
        np.column_stack(win_entry_cols), index=idx, columns=mi,
    )
    win_exits_df = pd.DataFrame(
        np.column_stack(win_exit_cols), index=idx, columns=mi,
    )
    win_se_df = None
    win_sx_df = None
    if win_se_cols:
        win_se_df = pd.DataFrame(
            np.column_stack(win_se_cols), index=idx, columns=mi,
        )
    if win_sx_cols:
        win_sx_df = pd.DataFrame(
            np.column_stack(win_sx_cols), index=idx, columns=mi,
        )

    winner_pf = simulator.run_backtest(
        price_df=price_data,
        entries_series=win_entries_df,
        exits_series=win_exits_df,
        short_entries_series=win_se_df,
        short_exits_series=win_sx_df,
        frequency=freq,
        **sim_kwargs,
    )

    if winner_pf is None:
        return _err("Winner re-simulation failed.", price_data)

    # Build final results with corrected portfolio_col_int_idx
    top5 = []
    for metric, info in winners:
        saved = info["_saved_signals"]
        col = saved["col_label"]
        col_key = col if not isinstance(col, list) else tuple(col)
        new_idx = seen_cols[col_key]

        row = {k: v for k, v in info.items() if not k.startswith("_")}
        row["portfolio_col_int_idx"] = new_idx
        top5.append(row)

    logger.info(f"{tag} Chunked simulation complete. {len(top5)} winner(s) found.")
    return {"top5": top5, "error": None, "portfolio": winner_pf, "price_data": price_data}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _save_col_signals(
    col,
    entries: pd.DataFrame,
    exits: pd.DataFrame,
    short_entries: pd.DataFrame | None,
    short_exits: pd.DataFrame | None,
) -> dict:
    """Saves one column's worth of signals (tiny: 1 col × n_rows bools)."""
    return {
        "col_label": col,
        "entry": entries[col].values.copy(),
        "exit": exits[col].values.copy(),
        "short_entry": short_entries[col].values.copy() if short_entries is not None else None,
        "short_exit": short_exits[col].values.copy() if short_exits is not None else None,
    }


def _is_better(candidate: dict, current: dict, metric: str) -> bool:
    """Returns True if candidate beats current for the given metric."""
    key_map = {
        "Best Sharpe": "sharpe_ratio",
        "Best Return": "total_return_pct",
        "Best Win Rate": "win_rate_pct",
    }
    key = key_map.get(metric)
    if key is None:
        return False

    c = candidate.get(key)
    b = current.get(key)

    if c is None:
        return False
    if b is None:
        return True
    return c > b


def _err(msg: str, price_data=None) -> dict:
    logger.warning(msg)
    return {"top5": [], "error": msg, "portfolio": None, "price_data": price_data}
