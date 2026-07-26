# options/execution.py
"""Shared trade→option execution engine.

Extracted from ``options/backtests/signal_overlay.py`` so that both the
dashboard overlay and the nn_meta label builder execute stock-signal trades as
option orders through the SAME machinery: contract selection as-of the entry
date, per-trade bar stitching, and expiry rolls.

The overlay imports these under their original underscore names; nn_meta uses
the public names. Caps (max rolls / max fills) come from the ``options_config``
dict passed to :class:`Execution`, so callers with heavier workloads (15-minute
label generation) can raise them without touching the dashboard defaults.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd

from utils.logging_utils import setup_logging
from options.selection import contract_selector

logger = setup_logging(log_file="logs/backtester.log")

_TAG = "OPT-EXEC"


def to_naive_utc(ts: pd.Timestamp) -> pd.Timestamp:
    """Massive option bars are tz-naive UTC; align underlying timestamps."""
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts


def extract_trades(single_pf) -> list[tuple[pd.Timestamp, pd.Timestamp, int]]:
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


class Execution:
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
        # Realistic fills (default): enter at the first option bar STRICTLY
        # after the signal bar's start — its open is at/after the signal
        # close, so the fill never uses a price from before the signal was
        # knowable. FILL_SAME_BAR=True restores the legacy convention
        # (entry at the signal bar's own open, ~one bar optimistic).
        self.fill_same_bar = bool(options_config.get("FILL_SAME_BAR", False))
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


def execute_variant(ex: Execution, stock_trades, und_close, und_index_utc,
                    target_dte: int, progress=None, daily: bool = False,
                    collect_marks: bool = False):
    """Execute the trade timeline at one target DTE.

    Returns (stitched OHLCV, entry timestamps, exit timestamps, blotter,
    n_rolls, capped) or None when nothing could be executed.

    ``collect_marks`` additionally attaches each leg's intratrade bar closes
    (``bar_ts`` / ``bar_close``) to its blotter entry.  These are the same bars
    the leg's return is computed from, so a mark stream built from them is
    consistent with the label by construction — no second pass over the raw
    contract bars, and no way for the two to disagree.  Off by default: the
    live scorer executes one trade at a time and has no use for the arrays.
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
        cur = to_naive_utc(ent_ts)
        exit_target = to_naive_utc(ext_ts)
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

            # Roll re-entries (hops > 0) are already causal: cur is the first
            # underlying bar strictly after the expired contract's last close.
            entry_side = "left" if (ex.fill_same_bar or hops > 0) else "right"
            epos = int(bars.index.searchsorted(cur, side=entry_side))
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
            leg = {
                "trade_idx": t_i, "contract": contract.symbol, "right": right,
                "strike": contract.strike,
                "expiration": contract.expiration.isoformat(),
                "entry": str(chunk.index[0]), "exit": str(chunk.index[-1]),
                "entry_open": float(chunk["Open"].iloc[0]),
                "exit_close": float(chunk["Close"].iloc[-1]),
            }
            if collect_marks:
                leg["bar_ts"] = chunk.index.to_numpy()
                leg["bar_close"] = chunk["Close"].to_numpy(dtype=float)
            blotter.append(leg)

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


def execute_trade_returns(ex: Execution, stock_trades, und_close, und_index_utc,
                          target_dte: int, *, fees: float = 0.001,
                          slippage: float = 0.0005, daily: bool = False,
                          progress=None, collect_marks: bool = False
                          ) -> tuple[list[dict], dict]:
    """Per-trade net option returns for a proposed trade timeline at one DTE.

    Labels for meta-training: each proposed stock trade is executed through
    :func:`execute_variant` (same contract selection, stitching, and rolls as
    the dashboard overlay), then its fills are compounded into one net return
    with the same per-side cost haircut the simulator applies::

        net = Π_fills (exit_close·(1−c)) / (entry_open·(1+c)) − 1,  c = fees+slippage

    Returns ``(records, meta)``. One record per proposed trade — including
    trades that could NOT be filled (``executed=False``, ``net_return=None``),
    so the caller can measure fill-failure and fill-lag quality:

        trade_idx, entry_ts, exit_ts, direction, right, target_dte,
        executed, net_return, n_fills, n_rolls,
        contract, strike, expiration, entry_premium (first fill),
        fill_entry_ts, fill_lag_s (seconds from signal entry to first fill)

    ``meta``: n_signals, n_executed, n_fills, n_rolls, capped, fill_fail_rate.
    """
    c = fees + slippage
    result = execute_variant(ex, stock_trades, und_close, und_index_utc,
                             target_dte, progress=progress, daily=daily,
                             collect_marks=collect_marks)
    fills_by_trade: dict[int, list[dict]] = {}
    capped = False
    n_rolls = 0
    if result is not None:
        _, _, _, blotter, n_rolls, capped = result
        for fill in blotter:
            fills_by_trade.setdefault(int(fill["trade_idx"]), []).append(fill)

    records: list[dict] = []
    for t_i, (ent_ts, ext_ts, direction) in enumerate(stock_trades):
        right = "C" if direction == 0 else "P"
        fills = fills_by_trade.get(t_i, [])
        rec = {
            "trade_idx": t_i, "entry_ts": pd.Timestamp(ent_ts),
            "exit_ts": pd.Timestamp(ext_ts), "direction": direction,
            "right": right, "target_dte": target_dte,
            "executed": bool(fills), "net_return": None, "gross_return": None,
            "n_fills": len(fills), "n_rolls": max(len(fills) - 1, 0),
            "contract": None, "strike": None, "expiration": None,
            "entry_premium": None, "fill_entry_ts": None, "fill_exit_ts": None,
            "fill_lag_s": None,
        }
        if fills:
            growth, gross_growth = 1.0, 1.0
            for f in fills:
                growth *= (f["exit_close"] * (1 - c)) / (f["entry_open"] * (1 + c))
                gross_growth *= f["exit_close"] / f["entry_open"]
            first = fills[0]
            fill_ts = pd.Timestamp(first["entry"])
            signal_ts = to_naive_utc(ent_ts)
            if daily:                      # executor compares by calendar day
                signal_ts = signal_ts.normalize()
            rec.update({
                "net_return": growth - 1.0,
                "gross_return": gross_growth - 1.0,
                "contract": first["contract"], "strike": first["strike"],
                "expiration": first["expiration"],
                "entry_premium": first["entry_open"],
                "fill_entry_ts": fill_ts,
                "fill_exit_ts": pd.Timestamp(fills[-1]["exit"]),
                "fill_lag_s": float((fill_ts - signal_ts).total_seconds()),
            })
        records.append(rec)

    n_exec = sum(r["executed"] for r in records)
    meta = {
        "n_signals": len(stock_trades), "n_executed": n_exec,
        "n_fills": sum(r["n_fills"] for r in records), "n_rolls": n_rolls,
        "capped": capped,
        "fill_fail_rate": 1.0 - n_exec / len(stock_trades) if stock_trades else 0.0,
    }
    if collect_marks:
        # Per-trade legs in fill order — the caller (which knows symbol/strategy)
        # turns these into a keyed mark stream.  Kept out of the record dicts so
        # the dataset rows stay flat and parquet-writable.
        meta["blotter"] = fills_by_trade
    return records, meta
