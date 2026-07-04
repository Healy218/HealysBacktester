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

from datetime import date, timedelta
from typing import Optional

import pandas as pd

from utils.logging_utils import setup_logging
from utils import freq_utils, runner_utils, param_utils
from portfolio import simulator
from options.data.provider import OptionsDataProvider
from options.selection import contract_selector
from options.backtests.run_options_single import _default_provider, _options_sim_kwargs

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


def _to_naive_utc(ts: pd.Timestamp) -> pd.Timestamp:
    """Massive option bars are tz-naive UTC; align underlying timestamps."""
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts


def _extract_trades(single_pf) -> list[tuple[pd.Timestamp, pd.Timestamp, int]]:
    """(entry_ts, exit_ts, direction) per executed trade, chronological.
    Open trades exit at the final bar (vectorbt already records them so).

    vectorbt 0.27 exposes ``trades.records`` as a DataFrame and the structured
    numpy array as ``records_arr``; older versions only have the array form.
    """
    trades = single_pf.trades
    recs = trades.records if isinstance(trades.records, pd.DataFrame) \
        else pd.DataFrame(trades.records_arr)
    idx = single_pf.wrapper.index
    out = []
    for r in recs.itertuples():
        out.append((pd.Timestamp(idx[int(r.entry_idx)]),
                    pd.Timestamp(idx[int(r.exit_idx)]),
                    int(r.direction)))
    out.sort(key=lambda t: t[0])
    return out


class _Execution:
    """Shared per-run state: provider, caches, and contract selection."""

    def __init__(self, symbol, interval, end_date, provider, options_config):
        self.symbol = symbol
        self.interval = interval
        self.end_d = pd.Timestamp(end_date).date()
        self.provider = provider
        self.target_delta = float(options_config.get("TARGET_DELTA", 0.50))
        self.moneyness = float(options_config.get("MONEYNESS", 0.0))
        self.max_rolls = int(options_config.get("MAX_ROLLS_PER_TRADE", 60))
        self.max_fills = int(options_config.get("MAX_FILLS_PER_VARIANT", 400))
        self._chain_cache: dict = {}
        self._bars_cache: dict = {}

    def bars(self, occ: str, frm: date, to: date) -> pd.DataFrame:
        if occ not in self._bars_cache:
            b = self.provider.get_contract_bars(occ, frm.isoformat(), to.isoformat(),
                                                self.interval)
            if (b is None or b.empty) and self.interval not in ("1d", "1D"):
                logger.info(f"[{_TAG}] {occ}: no {self.interval} bars, falling back to 1D")
                b = self.provider.get_contract_bars(occ, frm.isoformat(), to.isoformat(), "1D")
            self._bars_cache[occ] = b if b is not None else pd.DataFrame()
        return self._bars_cache[occ]

    def select(self, as_of: date, right: str, spot: float, target_dte: int):
        key = (as_of, right, target_dte)
        if key not in self._chain_cache:
            self._chain_cache[key] = self.provider.get_chain(
                self.symbol, right=right,
                expiration_gte=as_of + timedelta(days=max(1, target_dte - 10)),
                expiration_lte=as_of + timedelta(days=target_dte + 20),
                strike_gte=spot * 0.85, strike_lte=spot * 1.15,
                as_of=as_of,
            )
        chain = self._chain_cache[key]
        if not chain:
            return None
        return contract_selector.select_contract(
            chain, right=right, spot=spot, target_dte=target_dte,
            target_delta=self.target_delta, moneyness=self.moneyness, as_of=as_of,
        )


def _execute_variant(ex: _Execution, stock_trades, und_close, und_index_utc,
                     target_dte: int, progress=None, daily: bool = False):
    """Execute the trade timeline at one target DTE.

    Returns (stitched OHLCV, entry timestamps, exit timestamps, blotter,
    n_rolls, capped) or None when nothing could be executed.
    """
    slices: list[pd.DataFrame] = []
    entry_ts_list: list[pd.Timestamp] = []
    exit_ts_list: list[pd.Timestamp] = []
    blotter: list[dict] = []
    n_rolls = 0
    capped = False
    last_stitched: Optional[pd.Timestamp] = None

    for t_i, (ent_ts, ext_ts, direction) in enumerate(stock_trades):
        if progress:
            progress(t_i)
        if len(blotter) >= ex.max_fills:
            capped = True
            break
        right = "C" if direction == 0 else "P"
        cur = _to_naive_utc(ent_ts)
        exit_target = _to_naive_utc(ext_ts)
        if daily:
            # Daily bars carry vendor-specific times-of-day (Alpaca ~04:00 UTC,
            # Massive midnight): compare by calendar day or every entry lands
            # one bar late — fatal for 1-DTE contracts with only two bars.
            cur = cur.normalize()
            exit_target = exit_target.normalize()
        hops = 0

        while cur is not None and hops <= ex.max_rolls and len(blotter) < ex.max_fills:
            as_of = cur.date()
            spot_hist = und_close[und_index_utc <= cur]
            if spot_hist.empty:
                break
            spot = float(spot_hist.iloc[-1])
            contract = ex.select(as_of, right, spot, target_dte)
            if contract is None:
                logger.warning(f"[{_TAG}] no contract for {ex.symbol} {right} "
                               f"@ {as_of} ({target_dte} DTE)")
                break
            bars = ex.bars(contract.symbol, as_of,
                           min(contract.expiration + timedelta(days=1), ex.end_d))
            if bars.empty:
                break

            epos = int(bars.index.searchsorted(cur))
            while epos < len(bars) and last_stitched is not None \
                    and bars.index[epos] <= last_stitched:
                epos += 1
            if epos >= len(bars):
                break
            xpos = int(bars.index.searchsorted(exit_target, side="right")) - 1
            xpos = min(max(xpos, epos), len(bars) - 1)
            if xpos <= epos:
                break   # nothing tradable between fill and exit

            chunk = bars.iloc[epos:xpos + 1]
            slices.append(chunk)
            entry_ts_list.append(chunk.index[0])
            exit_ts_list.append(chunk.index[-1])
            last_stitched = chunk.index[-1]
            blotter.append({
                "contract": contract.symbol, "right": right,
                "strike": contract.strike,
                "expiration": contract.expiration.isoformat(),
                "entry": str(chunk.index[0]), "exit": str(chunk.index[-1]),
            })

            # contract ran out before the stock trade exited -> roll
            if chunk.index[-1] < exit_target and hops < ex.max_rolls:
                nxt = int(und_index_utc.searchsorted(chunk.index[-1], side="right"))
                if nxt < len(und_index_utc) and und_index_utc[nxt] < exit_target:
                    cur = und_index_utc[nxt]
                    hops += 1
                    n_rolls += 1
                    continue
            cur = None

    if not slices:
        return None
    stitched = pd.concat(slices)
    stitched = stitched[~stitched.index.duplicated(keep="first")].sort_index()
    return stitched, entry_ts_list, exit_ts_list, blotter, n_rolls, capped


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
