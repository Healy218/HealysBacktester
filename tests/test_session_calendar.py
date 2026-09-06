import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.live.feeds.barstore import aggregate_15m


def calendar():
    return SessionCalendar({"coverage_start": "2025-03-01", "coverage_end": "2026-12-31",
        "sessions": [{"date": "2025-03-07", "open": "09:30", "close": "16:00"},
                     {"date": "2025-03-10", "open": "09:30", "close": "16:00"},
                     {"date": "2025-07-03", "open": "09:30", "close": "13:00"},
                     {"date": "2026-09-08", "open": "09:30", "close": "16:00"}]})


def test_holiday_early_close_stagger_and_dst():
    c = calendar()
    assert c.bounds("2025-03-07")[0].hour == 14
    assert c.bounds("2025-03-10")[0].hour == 13
    assert len(c.closed_starts("2025-07-03", "2025-07-03T20:00Z")) == 14
    assert c.scan_open("2025-07-03T17:03:59Z")
    assert not c.scan_open("2025-07-03T17:04:00Z")
    assert not c.scan_open("2026-09-07T15:00Z")
    assert c.scan_open("2026-09-08T15:00Z")


def test_missing_calendar_coverage_is_not_assumed_holiday():
    with pytest.raises(ValueError, match="does not cover"):
        calendar().closed_starts("2027-01-04", "2027-01-04T20:00Z")


def test_early_close_stream_discards_post_session_and_forming_bars():
    index = pd.date_range("2025-07-03T13:30", "2025-07-03T20:00", freq="min")
    data = pd.DataFrame({k: 1. for k in ("Open", "High", "Low", "Close", "Volume")}, index=index)
    result = aggregate_15m(data, now=pd.Timestamp("2025-07-03T20:00Z"), calendar=calendar())
    assert len(result) == 14 and result.index[-1] == pd.Timestamp("2025-07-03T16:45")
    assert len(aggregate_15m(data, now=pd.Timestamp("2025-07-03T16:59Z"), calendar=calendar())) == 13


def test_configured_v6_requires_captured_calendar(monkeypatch, tmp_path):
    from nn_meta import config
    from nn_meta.session_calendar import configured_calendar
    monkeypatch.setattr(config, "POOL", "v6")
    monkeypatch.setattr(config, "DATA_CACHE", tmp_path)
    monkeypatch.delenv("NN_META_SESSION_CALENDAR", raising=False)
    with pytest.raises(ValueError, match="required"):
        configured_calendar()
