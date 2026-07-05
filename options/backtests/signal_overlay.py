# options/backtests/signal_overlay.py
"""Options execution overlay: run ANY strategy's signals as option orders,
swept across a grid of target expirations (DTEs) and ranked.

Model
-----
1. Run the wrapped strategy runner unchanged (parameter sweep on the
   UNDERLYING) and take its best parameter set's executed trade timeline
   (entry/exit timestamps + direction) straight from the vectorbt trade
   records — stops, trend filters and shorting behave exactly as in stock
   mode because they shaped that timeline.
2. For EACH target DTE in ``TARGET_DTE_GRID``, re-execute every trade as a
   single-leg option order: long trade -> buy a CALL, short trade -> buy a
   PUT, selected as-of the entry date by that DTE + delta/moneyness.
3. If a contract expires while the stock trade is still open, ROLL: exit at
   the contract's last bar and re-enter a fresh contract selected as of that
   date. A 1-DTE variant therefore becomes a rolling strategy that re-enters
   at every expiry while the signal stays on.
4. Each variant's traded contract windows are stitched into one series and
   simulated through the existing equity engine as its own one-column
   portfolio. The leaderboard ranks the variants by Sharpe, so the top-5
   table answers "which expiration profile trades this strategy best."

Returned dict matches ``backtests/run_*.py`` except that ``portfolio`` and
``option_series`` are dicts keyed by variant label (e.g. ``"5 DTE"``); each
top5 row carries its ``variant`` key so the dashboard can look up the right
portfolio (single column, ``portfolio_col_int_idx`` = 0).
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from utils.logging_utils import setup_logging
from utils import freq_utils, runner_utils, param_utils
from portfolio import simulator
from options.data.provider import OptionsDataProvider
from options.backtests.run_options_single import _default_provider, _options_sim_kwargs
# Execution engine lives in options/execution.py (shared with nn_meta);
# underscore aliases preserve this module's original internal names.
from options.execution import (
    Execution as _Execution,
    execute_variant as _execute_variant,
    extract_trades as _extract_trades,
    to_naive_utc as _to_naive_utc,
)

logger = setup_logging(log_file="logs/backtester.log")

_TAG = "OPT-OVERLAY"
MAX_OPTION_SIGNALS = 300        # stock trades per run (guards intraday signal spam)
DEFAULT_DTE_GRID = [1, 5, 10, 15, 30, 45]


def wrap(base_runner, options_config: dict):
    """Return a runner-shaped object executing ``base_runner`` signals as options."""
    return _OverlayRunner(base_runner, options_config or {})


class _OverlayRunner:
    def __init__(self, base_runner, options_config: dict):
        self._base = base_runner
        self._opts = options_config

    def run(self, symbol, start_date, end_date, interval,
            backtest_config, strategy_config, progress_callback=None):
        return run_overlay(
            symbol, start_date, end_date, interval, backtest_config,
            strategy_config, self._base, self._opts,
            progress_callback=progress_callback,
        )


def run_overlay(
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str,
    backtest_config: dict,
    strategy_config: dict,
    base_runner,
    options_config: dict,
    progress_callback=None,
    provider: Optional[OptionsDataProvider] = None,
) -> dict:
    try:
        cb = progress_callback or (lambda i, n: None)

        # ── 1) Stock-mode sweep on the underlying (60% of the progress bar) ──
        base = base_runner.run(
            symbol, start_date, end_date, interval, backtest_config,
            strategy_config,
            progress_callback=lambda i, n: cb(int((i + 1) / max(n, 1) * 60), 100),
        )
        if base.get("error"):
            return base
        top5 = base.get("top5") or []
        portfolio = base.get("portfolio")
        underlying = base.get("price_data")
        if not top5 or portfolio is None or underlying is None:
            return runner_utils.err("Strategy produced no results to execute as options.",
                                    _TAG, logger)

        best = top5[0]
        col = portfolio.wrapper.columns[int(best["portfolio_col_int_idx"])]
        single_pf = portfolio[col]
        stock_trades = _extract_trades(single_pf)
        if not stock_trades:
            return runner_utils.err("Best parameter set produced no trades.", _TAG, logger)
        if len(stock_trades) > MAX_OPTION_SIGNALS:
            return runner_utils.err(
                f"{len(stock_trades)} signals is too many for per-trade option "
                f"execution (max {MAX_OPTION_SIGNALS}). Use a coarser interval or a "
                f"less active parameter set.", _TAG, logger)

        if provider is None:
            provider = _default_provider()
        dte_grid = list(options_config.get("TARGET_DTE_GRID") or []) \
            or [int(options_config.get("TARGET_DTE", 30))]
        ex = _Execution(symbol, interval, end_date, provider, options_config)

        daily = interval in ("1d", "1D")
        und_close = underlying["Close"]
        und_index_utc = pd.DatetimeIndex([_to_naive_utc(t) for t in underlying.index])
        if daily:
            und_index_utc = und_index_utc.normalize()
        freq = freq_utils.resolve_freq(backtest_config.get("DEFAULT_FREQ"), interval)
        sim_kwargs = _options_sim_kwargs(backtest_config, options_config)
        base_label = best.get("param_label", "best")

        # ── 2) Execute the timeline once per target DTE, simulate each ───────
        portfolios: dict = {}
        option_series: dict = {}
        blotters: dict = {}
        rows: list[dict] = []
        n_var = len(dte_grid)

        for v_i, dte in enumerate(dte_grid):
            def _prog(t_i, _v=v_i):
                frac = (_v + t_i / max(len(stock_trades), 1)) / n_var
                cb(60 + int(frac * 38), 100)

            variant = f"{dte} DTE"
            result = _execute_variant(ex, stock_trades, und_close, und_index_utc,
                                      dte, progress=_prog, daily=daily)
            if result is None:
                logger.warning(f"[{_TAG}] {symbol} {variant}: no executable option trades")
                continue
            stitched, ent_ts, ext_ts, blotter, n_rolls, capped = result

            entries = pd.Series(False, index=stitched.index)
            exits = pd.Series(False, index=stitched.index)
            entries.loc[ent_ts] = True
            exits.loc[ext_ts] = True
            pf = simulator.run_backtest(
                price_df=stitched,
                entries_series=entries.to_frame(name=variant),
                exits_series=exits.to_frame(name=variant),
                frequency=freq,
                **sim_kwargs,
            )
            if pf is None:
                logger.warning(f"[{_TAG}] {symbol} {variant}: simulation returned nothing")
                continue

            row = param_utils._make_row_from_index(pf, 0, "Options exec")
            row["variant"] = variant
            row["param_label"] = (
                f"{variant} — {len(blotter)} fills"
                + (f", {n_rolls} rolls" if n_rolls else "")
                + (" (capped)" if capped else "")
                + f" [{base_label}]"
            )
            rows.append(row)
            portfolios[variant] = pf
            option_series[variant] = stitched
            blotters[variant] = blotter
            logger.info(f"[{_TAG}] {symbol} {variant}: {len(stock_trades)} trades → "
                        f"{len(blotter)} fills ({n_rolls} rolls)")

        if not rows:
            return runner_utils.err(
                "No option trades could be executed at any target DTE (no fills, "
                "chain gaps, or missing contract history).", _TAG, logger)

        # ── 3) Rank variants by Sharpe for the leaderboard ────────────────────
        rows.sort(key=lambda r: (r.get("sharpe_ratio") is None,
                                 -(r.get("sharpe_ratio") or 0)))
        for k, row in enumerate(rows, start=1):
            row["ranked_by"] = "Best Sharpe" if k == 1 else f"Sharpe #{k}"

        cb(100, 100)
        return {"top5": rows, "error": None, "portfolio": portfolios,
                "price_data": underlying, "option_series": option_series,
                "option_blotter": blotters}

    except Exception as e:
        logger.exception(f"[{_TAG}] Unexpected error: {e}")
        return runner_utils.err(str(e), _TAG, logger)
