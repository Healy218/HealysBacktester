from datetime import datetime

import pytest

from nn_meta.v7_plan import build_plan, completed_session


def calendar():
    return {"timezone": "America/New_York", "coverage_start": "2026-09-11",
        "coverage_end": "2026-09-16", "sessions": [
            {"date": "2026-09-11", "close": "16:00"},
            {"date": "2026-09-14", "close": "16:00"},
            {"date": "2026-09-15", "close": "16:00"}]}


@pytest.mark.parametrize("instant,expected", [
    ("2026-09-14T19:59:59+00:00", "2026-09-11"),
    ("2026-09-14T20:00:00+00:00", "2026-09-14"),
    ("2026-09-15T04:34:36+00:00", "2026-09-14"),
])
def test_completed_session_excludes_partial_day(instant, expected):
    assert completed_session(calendar(), datetime.fromisoformat(instant)) == expected


def test_early_close_respects_actual_session():
    cal = calendar()
    cal["sessions"][1]["close"] = "13:00"
    assert completed_session(cal, datetime.fromisoformat("2026-09-14T17:00:00+00:00")) == "2026-09-14"


@pytest.mark.parametrize("instant", ["2026-09-14T20:00:00", "2026-09-17T20:00:00+00:00"])
def test_cutoff_requires_timezone_and_calendar_coverage(instant):
    with pytest.raises(ValueError):
        completed_session(calendar(), datetime.fromisoformat(instant))


def test_v7_has_new_history_and_no_inherited_training_split_or_readiness():
    plan = build_plan(["SPY"], calendar(), as_of=datetime.fromisoformat("2026-09-15T04:34:36+00:00"))
    assert plan["historical_window"] == ["2022-03-07", "2026-09-14"]
    assert plan["version"] == "v7"
    assert plan["train_window"] is None
    assert plan["evaluation_policy"]["inherit_v6_dates"] is False
    assert plan["ready_for_build"] is False
    assert plan["execution"]["synthetic_historical_spreads"] is False
    assert plan["catalog"]["signal_minutes"] == [1, 5, 15, 30]
