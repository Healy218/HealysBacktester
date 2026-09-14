"""Frozen-selection execution stress and independent cash-ledger replay.

No policy search happens here. Both candidate and baseline use the same
execution rules. Quote spreads are paid by buying ask/selling bid; commission
is dollars per contract, not an extra percentage spread approximation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np
import pandas as pd

from nn_meta.v4_accounting import (AccountingDataError, UnfundedEntryError, CostScenario, FillPolicy,
    classify_quote, mark_to_market_portfolio, validate_execution_rows, validate_marks)


@dataclass(frozen=True)
class QuotePolicy:
    name: str = "quotes_base"
    max_entry_delay_seconds: float = 300.0
    submit_delay_seconds: float = 1.0
    max_quote_age_seconds: float = 30.0
    max_half_spread_bps: float = 500.0
    mark_interval_seconds: float = 900.0
    commission_per_contract: float = 0.65
    slippage_bps: float = 0.0

    def __post_init__(self):
        if not self.name.isidentifier():
            raise ValueError("quote scenario needs an identifier name")
        for key, value in asdict(self).items():
            if key != "name" and (not math.isfinite(value) or value < 0):
                raise ValueError(f"invalid quote policy {key}")
        if (self.max_quote_age_seconds <= 0 or self.mark_interval_seconds <= 0
                or self.submit_delay_seconds <= 0 or self.submit_delay_seconds > self.max_entry_delay_seconds
                or self.slippage_bps >= 10000):
            raise ValueError("invalid quote latency, cadence or slippage")


QUOTE_SCENARIOS = (
    QuotePolicy(),
    QuotePolicy(name="quotes_stressed", commission_per_contract=1.30, slippage_bps=25),
    QuotePolicy(name="quotes_severe", commission_per_contract=1.95, slippage_bps=50),
)


def utc(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise AccountingDataError("quote execution timestamps require explicit UTC/timezone")
    return stamp.tz_convert("UTC")


class QuoteTape:
    """As-of receipt lookup; an invalid new quote supersedes an older valid one."""

    def __init__(self, frame):
        required = {"contract", "quote_ts", "available_at", "bid", "ask", "bid_size", "ask_size"}
        if not required <= set(frame):
            raise AccountingDataError(f"quote tape missing columns: {sorted(required - set(frame))}")
        frame = frame.copy()
        for col in ("quote_ts", "available_at"):
            frame[col] = pd.DatetimeIndex([utc(t) for t in frame[col]])
        if (frame.available_at < frame.quote_ts).any():
            raise AccountingDataError("quote receipt precedes event timestamp")
        frame["contract"] = frame.contract.str.upper().str.removeprefix("O:")
        if frame.contract.isna().any() or (frame.contract == "").any():
            raise AccountingDataError("quote contract is missing")
        frame = frame.drop_duplicates()
        if frame.duplicated(["contract", "available_at"]).any():
            raise AccountingDataError("ambiguous same-receipt quotes need a sequenced source export")
        self.groups = {}
        for contract, group in frame.groupby("contract", sort=False):
            group = group.sort_values("available_at")
            # A delayed older event cannot replace a more recent book update.
            newest = group.quote_ts.cummax()
            self.groups[contract] = group[group.quote_ts >= newest].reset_index(drop=True)

    def quote(self, contract, timestamp, policy):
        timestamp = utc(timestamp)
        group = self.groups.get(contract)
        if group is None:
            return None, "missing_quote"
        i = group.available_at.searchsorted(timestamp, side="right") - 1
        if i < 0:
            return None, "missing_quote"
        q = group.iloc[i]
        try:
            sizes = np.asarray([q.bid_size, q.ask_size], dtype=float)
            if not np.isfinite(sizes).all() or (sizes <= 0).any():
                return None, "invalid_size"
        except (TypeError, ValueError):
            return None, "invalid_size"
        reason = classify_quote(q.bid, q.ask, quote_age=timestamp - q.quote_ts,
            policy=FillPolicy(max_half_spread_bps=policy.max_half_spread_bps,
                              max_staleness=pd.Timedelta(seconds=policy.max_quote_age_seconds)))
        return (None, reason.value) if reason else (q, None)

    def entry(self, contract, decision, exit_target, policy):
        ready = decision + pd.Timedelta(seconds=policy.submit_delay_seconds)
        deadline = min(decision + pd.Timedelta(seconds=policy.max_entry_delay_seconds), exit_target)
        group = self.groups.get(contract)
        times = [ready]
        if group is not None:
            times.extend(group.loc[(group.available_at > ready) &
                                   (group.available_at <= deadline), "available_at"])
        reason = "missing_quote"
        for stamp in times:
            if stamp > deadline or stamp >= exit_target:
                continue
            quote, reason = self.quote(contract, stamp, policy)
            if quote is not None:
                return stamp, quote, None
        return None, None, reason or "entry_latency_limit"


def aggregate_latency(trades, marks, *, max_delay_seconds, signal_interval_seconds=900):
    """Audit the retained selected positions; rejection does not backfill slots."""
    if not math.isfinite(max_delay_seconds) or max_delay_seconds < 0:
        raise ValueError("invalid aggregate latency limit")
    trades = validate_execution_rows(trades)
    delay = (trades.fill_entry_ts - trades.signal_ts).dt.total_seconds() - signal_interval_seconds
    keep = (delay >= 0) & (delay <= max_delay_seconds)
    rejected = trades.loc[~keep, ["trade_id"]].assign(
        reason=np.where(delay[~keep] < 0, "before_signal_close", "entry_latency_limit"),
        delay_seconds=delay[~keep].to_numpy())
    retained = trades.loc[keep].copy()
    return retained, marks[marks.trade_id.isin(retained.trade_id)].copy(), rejected


def admit_fills(trades, marks, *, max_concurrent):
    """Apply the same slot/symbol rules at actual fills; no replacement entries."""
    trades = validate_execution_rows(trades)
    open_positions, admitted, rejected = [], [], []
    for trade in trades.itertuples(index=False):
        open_positions = [p for p in open_positions if p.fill_exit_ts > trade.fill_entry_ts]
        reason = ("symbol_at_actual_fill" if any(p.symbol == trade.symbol for p in open_positions)
                  else "capacity_at_actual_fill" if len(open_positions) >= max_concurrent else None)
        if reason:
            rejected.append({"trade_id": trade.trade_id, "reason": reason})
        else:
            admitted.append(trade.trade_id)
            open_positions.append(trade)
    return trades[trades.trade_id.isin(admitted)], marks[marks.trade_id.isin(admitted)], pd.DataFrame(rejected)


def replay_quotes(plans, legs, tape, *, policy=QUOTE_SCENARIOS[0]):
    """Replay explicit frozen contract/roll plans into normalized dollar paths.

    Plans: trade_id, symbol, signal_ts, size_fraction (optional). Legs:
    trade_id, leg_index, contract, entry_decision_ts, exit_decision_ts,
    expiration_ts. All timestamps are timezone-aware. Missing initial entry
    rejects; missing exits/marks value an open option at zero, visibly flagged.
    A failed roll entry keeps proceeds as cash through the planned final exit.
    """
    required = {"trade_id", "leg_index", "contract", "entry_decision_ts",
                "exit_decision_ts", "expiration_ts"}
    if not {"trade_id", "symbol", "signal_ts"} <= set(plans) or not required <= set(legs):
        raise AccountingDataError("quote replay needs explicit frozen plans and complete legs")
    if plans.trade_id.duplicated().any() or legs.duplicated(["trade_id", "leg_index"]).any():
        raise AccountingDataError("duplicate plan/leg identity")
    if set(plans.trade_id) != set(legs.trade_id):
        raise AccountingDataError("every frozen position needs an exact complete leg plan")
    trades, marks, audit = [], [], []
    for plan in plans.itertuples(index=False):
        parts = legs[legs.trade_id == plan.trade_id].sort_values("leg_index").copy()
        if parts.leg_index.tolist() != list(range(len(parts))):
            raise AccountingDataError("roll indexes must be contiguous from zero")
        for col in ("entry_decision_ts", "exit_decision_ts", "expiration_ts"):
            parts[col] = pd.DatetimeIndex([utc(v) for v in parts[col]])
        signal = utc(plan.signal_ts)
        if ((parts.exit_decision_ts <= parts.entry_decision_ts).any()
                or (parts.exit_decision_ts > parts.expiration_ts).any()
                or parts.entry_decision_ts.iloc[0] < signal
                or (parts.entry_decision_ts.iloc[1:].to_numpy() <
                    parts.exit_decision_ts.iloc[:-1].to_numpy()).any()):
            raise AccountingDataError("noncausal, overlapping or expired frozen leg plan")
        end = parts.exit_decision_ts.iloc[-1]
        path = {}
        growth, gross_growth, turnover = 1.0, 1.0, 0.0
        first_entry = None
        entry_value = entry_turnover = None
        for leg in parts.itertuples(index=False):
            contract = leg.contract.upper().removeprefix("O:")
            from options.data.provider import parse_occ_symbol
            _, expiry, _, _ = parse_occ_symbol(contract)
            if leg.expiration_ts.tz_convert("America/New_York").date() != expiry:
                raise AccountingDataError("leg expiration disagrees with its OCC contract")
            entered, q, failure = tape.entry(contract, leg.entry_decision_ts, leg.exit_decision_ts, policy)
            if failure:
                audit.append(dict(trade_id=plan.trade_id, leg_index=leg.leg_index,
                                  side="entry", reason=failure, conservative=first_entry is not None))
                if first_entry is not None:
                    path[end] = (gross_growth - 1, growth - 1, turnover)
                break
            if first_entry is None:
                first_entry = entered
            ask = float(q.ask)
            buy = ask * (1 + policy.slippage_bps / 10000)
            commission = policy.commission_per_contract / 100.0
            units = growth / (buy + commission)
            gross_units = gross_growth / ask
            turnover += units * buy
            if entry_turnover is None:
                entry_turnover = turnover
                entry_value = units * float(q.bid) - 1
            group = tape.groups[contract]
            times = set(group.loc[(group.available_at >= entered) &
                                  (group.available_at <= leg.exit_decision_ts), "available_at"])
            # RTH-only cadence avoids fabricating weekend marks. The endpoints
            # are always retained; stale/missing scheduled observations are zero.
            for stamp in pd.date_range(entered, leg.exit_decision_ts,
                                       freq=pd.Timedelta(seconds=policy.mark_interval_seconds)):
                local = stamp.tz_convert("America/New_York")
                if local.weekday() < 5 and (9, 30) <= (local.hour, local.minute) <= (16, 0):
                    times.add(stamp)
            times.update([entered, leg.exit_decision_ts])
            for stamp in sorted(times):
                quote, reason = tape.quote(contract, stamp, policy)
                bid = float(quote.bid) if quote is not None else 0.0
                terminal = stamp == leg.exit_decision_ts
                if reason:
                    audit.append(dict(trade_id=plan.trade_id, leg_index=leg.leg_index,
                        side="exit" if terminal else "mark", timestamp=stamp.isoformat(),
                        reason=reason, conservative=True))
                value = units * bid
                gross_value = gross_units * bid
                if terminal:
                    sale = bid * (1 - policy.slippage_bps / 10000)
                    # No fill/commission is claimed for the conservative zero.
                    value = units * (sale - commission) if quote is not None else 0.0
                    turnover += units * sale
                    growth, gross_growth = value, gross_value
                path[stamp] = (gross_value - 1, value - 1, turnover)
            if growth <= 0:
                path[end] = (gross_growth - 1, growth - 1, turnover)
                break
        if first_entry is None:
            continue
        record = dict(trade_id=plan.trade_id, symbol=plan.symbol, signal_ts=signal,
            fill_entry_ts=first_entry, fill_exit_ts=end, gross_return=path[end][0],
            cost_model="option_quote", **{
                f"entry_turnover_{policy.name}": entry_turnover,
                f"entry_net_return_{policy.name}": entry_value})
        if hasattr(plan, "size_fraction"):
            record["size_fraction"] = plan.size_fraction
        trades.append(record)
        for stamp, (gross, net, turn) in sorted(path.items()):
            marks.append(dict(trade_id=plan.trade_id, mark_ts=stamp, gross_return=gross,
                **{f"net_return_{policy.name}": net, f"turnover_{policy.name}": turn - entry_turnover}))
    trade_cols = ["trade_id", "symbol", "signal_ts", "fill_entry_ts", "fill_exit_ts", "gross_return"]
    mark_cols = ["trade_id", "mark_ts", "gross_return"]
    return (pd.DataFrame(trades) if trades else pd.DataFrame(columns=trade_cols),
            pd.DataFrame(marks) if marks else pd.DataFrame(columns=mark_cols), pd.DataFrame(audit))


def independent_ledger(trades, marks, *, max_concurrent, position_fraction, costs):
    """Separate event/cash calculation; shares schema checks, no ledger helpers."""
    trades = validate_execution_rows(trades)
    marks = validate_marks(marks, trades)
    if not 0 < position_fraction <= 1 or max_concurrent < 1 or max_concurrent * position_fraction > 1:
        raise ValueError("invalid capital allocation")
    cash, holdings, curve, peak = 1.0, {}, [], 1.0
    explicit = "cost_model" in trades
    specs = {r.trade_id: r for r in trades.itertuples(index=False)}
    entries = {t: g for t, g in trades.groupby("fill_entry_ts")}
    by_time = {t: g for t, g in marks.groupby("mark_ts")}
    for stamp in sorted(set(entries) | set(by_time)):
        pending = list(by_time.get(stamp, pd.DataFrame()).itertuples(index=False))
        # Preexisting positions are updated before allocating new positions.
        for mark in pending:
            if mark.trade_id not in holdings:
                continue
            amount, _ = holdings[mark.trade_id]
            spec = specs[mark.trade_id]
            is_exit = stamp == spec.fill_exit_ts
            factor = (1 + getattr(mark, f"net_return_{costs.name}") if explicit else
                      (1 + mark.gross_return) * (1 - costs.side_cost) ** getattr(mark, "cost_exits", int(is_exit))
                      / (1 + costs.side_cost) ** getattr(mark, "cost_entries", 1))
            if is_exit:
                cash += amount * factor
                del holdings[mark.trade_id]
            else:
                holdings[mark.trade_id] = (amount, amount * factor)
        for trade in entries.get(stamp, pd.DataFrame()).itertuples(index=False):
            if len(holdings) >= max_concurrent or any(specs[i].symbol == trade.symbol for i in holdings):
                raise AccountingDataError("independent ledger slot/symbol conflict")
            fraction = getattr(trade, "size_fraction", position_fraction)
            if not math.isfinite(fraction) or not 0 < fraction <= position_fraction:
                raise AccountingDataError("invalid independent size fraction")
            amount = min(cash, fraction * (cash + sum(v for _, v in holdings.values())))
            if amount <= 0:
                raise UnfundedEntryError(timestamp=stamp, trade_id=trade.trade_id,
                    cash=cash, equity=cash + sum(v for _, v in holdings.values()))
            cash -= amount
            mark = next(m for m in pending if m.trade_id == trade.trade_id)
            factor = (1 + getattr(mark, f"net_return_{costs.name}") if explicit else
                      (1 + mark.gross_return) * (1 - costs.side_cost) ** getattr(mark, "cost_exits", 0)
                      / (1 + costs.side_cost) ** getattr(mark, "cost_entries", 1))
            if stamp == trade.fill_exit_ts:
                cash += amount * factor
            else:
                holdings[trade.trade_id] = (amount, amount * factor)
        nav = cash + sum(v for _, v in holdings.values())
        peak = max(peak, nav)
        curve.append(dict(timestamp=stamp, equity=nav, drawdown=(peak - nav) / peak))
    if holdings:
        raise AccountingDataError("independent ledger has unclosed positions")
    return pd.DataFrame(curve, columns=["timestamp", "equity", "drawdown"])


def checked_ledger(trades, marks, *, max_concurrent, position_fraction, costs,
                   allow_unfunded=False):
    if trades.empty:
        return {"n_positions": 0, "total_return": 0.0, "max_drawdown": 0.0,
                "independent_ledger_match": True}, pd.DataFrame()
    try:
        metrics, curve = mark_to_market_portfolio(trades, marks, max_concurrent=max_concurrent,
                                                 position_fraction=position_fraction, costs=costs)
    except UnfundedEntryError as exc:
        if not allow_unfunded:
            raise
        try:
            independent_ledger(trades, marks, max_concurrent=max_concurrent,
                               position_fraction=position_fraction, costs=costs)
        except UnfundedEntryError as other:
            if any(exc.details[k] != other.details[k] for k in ('timestamp', 'trade_id')):
                raise AccountingDataError("independent ledger rejects a different entry") from other
            if not np.allclose([exc.details[k] for k in ('cash', 'equity')],
                               [other.details[k] for k in ('cash', 'equity')], rtol=1e-10, atol=1e-12):
                raise AccountingDataError("independent ledger funding balances disagree") from other
        else:
            raise AccountingDataError("independent ledger unexpectedly funds rejected entry") from exc
        # A matched rejection is not a matched equity curve. No fabricated
        # return, zero-loss outcome or filled-position count is reported.
        return {"n_positions": 0, "selected_positions": len(trades),
                "total_return": None, "max_drawdown": None, "accounting_status": "unfunded",
                "accounting_failure": exc.details, "independent_ledger_match": False,
                "independent_rejection_match": True}, pd.DataFrame(columns=["timestamp", "equity"])
    other = independent_ledger(trades, marks, max_concurrent=max_concurrent,
                               position_fraction=position_fraction, costs=costs)
    if (not curve.timestamp.equals(other.timestamp)
            or not np.allclose(curve.equity, other.equity, rtol=1e-10, atol=1e-12)
            or not np.isclose(metrics["max_drawdown"], other.drawdown.max(), rtol=1e-10, atol=1e-12)):
        raise AccountingDataError("independent cash ledger disagrees with canonical accounting")
    metrics["independent_ledger_match"] = True
    return metrics, curve
