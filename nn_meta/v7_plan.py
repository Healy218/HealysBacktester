"""Draft V7 scope; a full-history declaration is never evidence of coverage."""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
from zoneinfo import ZoneInfo

from nn_meta.multitimeframe_catalog import canonical, registered_catalog

HISTORY_START = "2022-03-07"


def completed_session(calendar, as_of):
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must have a timezone")
    if calendar.get("timezone") != "America/New_York":
        raise ValueError("Expected a New York exchange calendar")
    local_date = as_of.astimezone(ZoneInfo("America/New_York")).date()
    if not (date.fromisoformat(calendar["coverage_start"]) <= local_date
            <= date.fromisoformat(calendar["coverage_end"])):
        raise ValueError("Calendar does not cover the cutoff observation date")
    sessions = calendar["sessions"]
    days = [s["date"] for s in sessions]
    if not days or days != sorted(set(days)):
        raise ValueError("Calendar sessions must be unique and ordered")
    completed = []
    for session in sessions:
        close = datetime.fromisoformat(f"{session['date']}T{session['close']}").replace(
            tzinfo=ZoneInfo("America/New_York"))
        if close <= as_of:
            completed.append(session["date"])
    if not completed:
        raise ValueError("No completed session")
    return completed[-1]


def build_plan(symbols, calendar, *, as_of):
    end = completed_session(calendar, as_of)
    if end < HISTORY_START:
        raise ValueError("No V7 history yet")
    result = {
        "schema": "v7-research-plan-draft-v1",
        "version": "v7",
        "name": f"v7-{HISTORY_START.replace('-', '')}-{end.replace('-', '')}",
        "status": "preparation_only",
        "ready_for_build": False,
        "historical_window": [HISTORY_START, end],
        "cutoff_observed_at": as_of.isoformat(),
        "cutoff_policy": "Latest completed regular session in the supplied exchange calendar",
        "warmup_policy": "Earlier observed inputs allowed for causal feature warmup; no pre-start option labels",
        "train_window": None,
        "evaluation_policy": {
            "status": "design_required_before_freeze",
            "inherit_v6_dates": False,
            "method": "Chronological walk-forward, purged by complete label horizons, with embargo",
            "selection": "Fit parameters, scalers and thresholds on each fold's training history only",
            "previously_inspected_periods": "Revalidation, never relabeled untouched holdout",
        },
        "actual_calendar_dte": [1, 9],
        "execution": {"cadence_minutes": 1, "source": "frozen MASSIVE observed bid/ask quotes",
            "synthetic_historical_spreads": False, "aggregate_fill_fallback": False},
        "feature_policy": {
            "scope": "Full existing suite including all thirteen TradingView scopes and option quote/trade features",
            "coverage": "Audit every feature dependency across the full window and each signal timeframe",
            "missing_history": "Block full-suite admission; no silent feature removal, fabricated values or date truncation",
            "schema": "Rebuild and version for V7; do not inherit the V6 feature hash",
        },
        "universe_policy": "Existing symbol inventory is a starting reference; rebuild historical PIT membership, aliases and listing coverage",
        "worker_target": 4,
        "catalog": registered_catalog(symbols),
        "required_before_launch": [
            "Full-window calendar and point-in-time universe",
            "Verified minute raw/adjusted underlying coverage and warmup",
            "Every feature dependency including prior-date chains, surfaces and market context",
            "All strategy/timeframe variants with bounded vectorization and causal parity",
            "Complete quote/trade capture, execution, marks and roll audits",
            "Frozen fold dates, model trials, costs, latency and portfolio rules",
            "Representative full-pipeline pilot, resource budget and immutable source/data manifests",
        ],
    }
    return {**result, "plan_sha256": sha256(canonical(result).encode()).hexdigest()}
