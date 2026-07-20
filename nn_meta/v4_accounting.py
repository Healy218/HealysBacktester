"""V4 option execution and mark-to-market accounting contract.

This module deliberately does not infer intratrade option marks from a final
``net_return``.  A report is marked-to-market only when it is supplied with
observed contract marks; otherwise it fails closed.  Legacy selection remains
available for historical comparison, but is not presented as V4 accounting.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CostScenario:
    """Per-side conservative execution assumptions, expressed as fractions."""

    name: str = "base"
    fee: float = 0.001
    slippage: float = 0.0005
    half_spread_bps: float = 0.0

    @property
    def side_cost(self) -> float:
        return self.fee + self.slippage + self.half_spread_bps / 10_000


BASE_COSTS = CostScenario()
STRESSED_COSTS = CostScenario(name="stressed", fee=0.002, slippage=0.001,
                              half_spread_bps=25.0)


class AccountingDataError(ValueError):
    """Raised when a dataset cannot support the requested V4 accounting."""


def validate_execution_rows(trades: pd.DataFrame) -> pd.DataFrame:
    """Validate causal fill times and normalize the V4 execution schema.

    Required fields are intentionally explicit: signal time is not assumed to
    be a fill, and a missing option exit fill is not silently replaced by an
    underlying price or an end-of-period value.
    """
    required = {"trade_id", "symbol", "signal_ts", "fill_entry_ts",
                "fill_exit_ts", "gross_return"}
    missing = required - set(trades.columns)
    if missing:
        raise AccountingDataError(f"missing V4 execution fields: {sorted(missing)}")
    out = trades.copy()
    for col in ("signal_ts", "fill_entry_ts", "fill_exit_ts"):
        out[col] = pd.to_datetime(out[col])
    if out["trade_id"].duplicated().any():
        raise AccountingDataError("trade_id must be unique")
    if (out["fill_entry_ts"] <= out["signal_ts"]).any():
        raise AccountingDataError("entry fill must occur strictly after the signal")
    if (out["fill_exit_ts"] < out["fill_entry_ts"]).any():
        raise AccountingDataError("exit fill precedes entry fill")
    if (~np.isfinite(out["gross_return"].astype(float))).any():
        raise AccountingDataError("gross_return must be finite")
    return out.sort_values(["fill_entry_ts", "trade_id"]).reset_index(drop=True)


def validate_marks(marks: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    """Ensure each position has observed entry and exit marks, no extrapolation.

    Any supplied intratrade marks become equity-curve events.  A future
    production gate can require a minimum mark cadence once the label builder
    persists the full option-bar path.
    """
    required = {"trade_id", "mark_ts", "gross_return"}
    missing = required - set(marks.columns)
    if missing:
        raise AccountingDataError(f"missing mark fields: {sorted(missing)}")
    out = marks.copy()
    out["mark_ts"] = pd.to_datetime(out["mark_ts"])
    out["gross_return"] = out["gross_return"].astype(float)
    if (~np.isfinite(out["gross_return"])).any():
        raise AccountingDataError("mark gross_return must be finite")
    bounds = trades.set_index("trade_id")[["fill_entry_ts", "fill_exit_ts"]]
    if not set(out["trade_id"]).issubset(bounds.index):
        raise AccountingDataError("marks reference an unknown trade")
    joined = out.join(bounds, on="trade_id")
    if ((joined["mark_ts"] < joined["fill_entry_ts"]) |
            (joined["mark_ts"] > joined["fill_exit_ts"])).any():
        raise AccountingDataError("mark lies outside its executed position")
    for trade in trades.itertuples():
        ts = out.loc[out["trade_id"] == trade.trade_id, "mark_ts"]
        if trade.fill_entry_ts not in set(ts) or trade.fill_exit_ts not in set(ts):
            raise AccountingDataError(f"trade {trade.trade_id} lacks an entry or exit mark")
    return out.sort_values(["mark_ts", "trade_id"]).reset_index(drop=True)


def mark_to_market_portfolio(trades: pd.DataFrame, marks: pd.DataFrame, *,
                             max_concurrent: int, position_fraction: float,
                             costs: CostScenario = BASE_COSTS) -> tuple[dict, pd.DataFrame]:
    """Return metrics and an event equity curve using observed contract marks.

    Positions are allocated from equity at their actual fill time.  Cash is
    debited at entry, option value is marked at every supplied mark, and exit
    costs are applied only at the exit fill.  A same-symbol or slot conflict
    is rejected rather than reinterpreted as a filled trade.
    """
    if max_concurrent < 1 or not 0 < position_fraction <= 1:
        raise ValueError("invalid concurrency or position fraction")
    if max_concurrent * position_fraction > 1:
        raise ValueError("configured gross exposure exceeds available capital")
    trades = validate_execution_rows(trades)
    marks = validate_marks(marks, trades)
    by_trade = {r.trade_id: r for r in trades.itertuples(index=False)}
    marks_by_time = {ts: grp for ts, grp in marks.groupby("mark_ts", sort=True)}
    events = sorted(set(trades["fill_entry_ts"]) | set(marks["mark_ts"]))
    cash, peak, max_dd = 1.0, 1.0, 0.0
    open_pos: dict[object, dict] = {}
    curve: list[dict] = []
    turnover = 0.0

    def equity() -> float:
        return cash + sum(p["value"] for p in open_pos.values())

    for ts in events:
        # Exit marks are processed before same-timestamp entries, freeing slots
        # only after the old position has received its actual closing value.
        for mark in marks_by_time.get(ts, pd.DataFrame()).itertuples(index=False):
            pos = open_pos.get(mark.trade_id)
            if pos is None:
                continue
            value = pos["notional"] * (1 + float(mark.gross_return)) / (1 + costs.side_cost)
            is_exit = ts == pos["trade"].fill_exit_ts
            if is_exit:
                cash += value * (1 - costs.side_cost)
                turnover += 2 * pos["notional"]
                del open_pos[mark.trade_id]
            else:
                pos["value"] = value
        for trade in trades[trades["fill_entry_ts"] == ts].itertuples(index=False):
            if len(open_pos) >= max_concurrent:
                raise AccountingDataError(f"slot cap exceeded at {ts}")
            if any(p["trade"].symbol == trade.symbol for p in open_pos.values()):
                raise AccountingDataError(f"overlapping {trade.symbol} position at {ts}")
            notional = position_fraction * equity()
            cash -= notional
            open_pos[trade.trade_id] = {"trade": trade, "notional": notional,
                                        "value": notional / (1 + costs.side_cost)}
        nav = equity()
        peak = max(peak, nav)
        max_dd = max(max_dd, (peak - nav) / peak)
        curve.append({"timestamp": ts, "equity": nav,
                      "gross_exposure": sum(p["value"] for p in open_pos.values()) / nav
                      if nav else np.nan,
                      "open_positions": len(open_pos)})
    if open_pos:
        raise AccountingDataError("open position lacks an exit mark")
    curve_df = pd.DataFrame(curve)
    metrics = {
        "total_return": float(curve_df["equity"].iloc[-1] - 1) if len(curve_df) else 0.0,
        "max_drawdown": float(max_dd), "turnover": float(turnover),
        "peak_gross_exposure": float(curve_df["gross_exposure"].max()) if len(curve_df) else 0.0,
        "mean_gross_exposure": float(curve_df["gross_exposure"].mean()) if len(curve_df) else 0.0,
        "n_positions": len(trades), "cost_scenario": costs.name,
    }
    return metrics, curve_df
