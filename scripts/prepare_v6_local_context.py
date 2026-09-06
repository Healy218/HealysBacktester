"""Seal explicit local research context; never claim observed TradingView parity.

Two-session groups are anchored to the first session in the supplied calendar.
VWAP resets on each New York trading date. Minimum tick is a fixed research
parameter, not inferred exchange metadata. Missing price bars are never filled.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from nn_meta.v6_expansion import (SCHEMA, DEFERRED_CONTRACT_VERSION, EXTRA_FEATURES,
    POLICY_VERSION, ExpandedInputs, aware_bars, bars_sha256, feature_schema, sha256)
from nn_meta.tradingview_features import validate_feature_inputs


def local_context(bars, calendar, *, symbol, minimum_tick):
    bars = aware_bars(bars)
    sessions = calendar["sessions"]
    dates = [s["date"] for s in sessions]
    if (not dates or dates != sorted(set(dates))
            or calendar["timezone"] != "America/New_York"):
        raise ValueError("calendar needs unique ordered New York sessions")
    lookup = {day: i for i, day in enumerate(dates)}
    local = bars.index.tz_convert("America/New_York")
    bar_dates = local.strftime("%Y-%m-%d")
    if bars.empty or any(day not in lookup for day in bar_dates):
        raise ValueError("every actual bar must belong to a declared calendar session")
    for day in set(bar_dates):
        session = sessions[lookup[day]]
        opens = pd.Timestamp(f"{day} {session['open']}", tz="America/New_York")
        closes = pd.Timestamp(f"{day} {session['close']}", tz="America/New_York")
        observed = local[bar_dates == day]
        if (observed < opens).any() or (observed + pd.Timedelta(minutes=15) > closes).any():
            raise ValueError(f"{symbol}: actual bar lies outside calendar RTH on {day}")
    groups = np.array([lookup[day] // 2 for day in bar_dates])
    flags = pd.DataFrame({
        "htf_change": np.r_[True, groups[1:] != groups[:-1]],
        "vwap_reset": np.r_[True, bar_dates[1:] != bar_dates[:-1]],
        "available_at": bars.index}, index=bars.index)
    context = {"minimum_tick": minimum_tick, "session_policy": "local_research",
        "as_of": (bars.index[-1] + pd.Timedelta(minutes=15)).isoformat(),
        "dependency_metadata": {"symbol": symbol,
            "calendar_id": f"local-research-calendar-anchored-{dates[0]}",
            "htf_period": "2D", "vwap_anchor": "local-research-New-York-date-reset",
            "timeframe_flag_basis": "local-research-consecutive-calendar-session-pairs",
            "chart_session": "local-provider-RTH-literal-membership-transitions",
            "history_origin": bars.index[0].isoformat(),
            "minimum_tick_basis": "fixed-research-assumption-not-exchange-verification",
            "external_context": "unverified-local-assumptions"}}
    validation = validate_feature_inputs(bars, timeframe_flags=flags, **context)
    context["dependency_metadata"]["ict_session_gaps"] = json.dumps(validation["ict_session_gap_count"], sort_keys=True)
    return flags, context


def prepare(args):
    output = args.output.absolute()
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("output must be fresh without symlinked parents")
    references = {str(p.absolute()): sha256(p) for p in (args.bars, args.calendar, args.tick_policy)}
    calendar = json.loads(args.calendar.read_bytes())
    policy = json.loads(args.tick_policy.read_bytes())
    panel = pd.read_parquet(args.bars)
    symbols = sorted(set(panel.symbol)) if not args.symbols else args.symbols.split(",")
    if (not symbols or len(set(symbols)) != len(symbols) or set(symbols) - set(panel.symbol)
            or any(not isinstance(s, str) or not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,15}", s) for s in symbols)):
        raise ValueError("symbols must be distinct names present in the panel")
    document = {"schema": SCHEMA, "feature_contract_version": DEFERRED_CONTRACT_VERSION,
        "feature_names": list(EXTRA_FEATURES), "selection_policy": POLICY_VERSION,
        "moneyness": 0., "tick_feature_policy": policy,
        "external_comparison": {"status": "deferred", "research_only": True,
            "reason": "User selected Option 1: local context assumptions, all 13 groups and tick features retained"},
        "feature_schema": feature_schema(minimum_tick=args.minimum_tick,
            session_policy="local_research", vwap_mode="reset_flags"),
        "context_references": [{"path": str(args.calendar.absolute()),
                                "sha256": references[str(args.calendar.absolute())]}],
        "local_context_policy": {"schema": "local-calendar-context-v1",
            "two_session_anchor": calendar["sessions"][0]["date"],
            "grouping": "floor(calendar_session_ordinal / 2)",
            "vwap_reset": "first actual bar of each New York date",
            "minimum_tick_assumption": args.minimum_tick,
            "missing_bars": "not synthesized", "external_context_verified": False,
            "source_inputs_sha256": references}, "symbols": {}}
    if args.run:
        output.mkdir(parents=True)
    for symbol in symbols:
        bars = panel.loc[panel.symbol == symbol].set_index("timestamp").sort_index()
        bars = bars[["Open", "High", "Low", "Close", "Volume"]]
        flags, context = local_context(bars, calendar, symbol=symbol, minimum_tick=args.minimum_tick)
        if args.run:
            path = output / f"{symbol}.flags.parquet"
            flags.to_parquet(path)
            document["symbols"][symbol] = {"bars_sha256": bars_sha256(bars), "context": context,
                "timeframe_flags": {"path": path.name, "sha256": sha256(path)}}
        print(json.dumps({"symbol": symbol, "bars": len(bars), "context_validated": True}), flush=True)
    if any(sha256(path) != digest for path, digest in references.items()):
        raise ValueError("context inputs changed during preparation")
    if args.run:
        path = output / "planning-inputs.json"
        path.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n")
        digest = sha256(path)
        ExpandedInputs(path, digest, parity_policy="deferred")
        (output / "manifest.json").write_text(json.dumps({"complete": True,
            "planning_inputs_sha256": digest, "symbol_count": len(symbols),
            "tick_stores_bound": False, "freeze_started": False}, indent=2) + "\n")
        print(json.dumps({"path": str(path), "sha256": digest, "symbols": len(symbols)}), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bars", type=Path, required=True)
    ap.add_argument("--calendar", type=Path, required=True)
    ap.add_argument("--tick-policy", type=Path, required=True)
    ap.add_argument("--minimum-tick", type=float, required=True)
    ap.add_argument("--symbols")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--run", action="store_true")
    prepare(ap.parse_args())


if __name__ == "__main__":
    main()
