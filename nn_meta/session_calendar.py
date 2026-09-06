"""Explicit exchange sessions shared by candidate research and live aggregation.

An absent date is a holiday only inside the calendar's declared coverage range.
Outside that range we refuse to guess. V6 requires a captured calendar; legacy
pool callers may retain their older hours rule until their coordinated rebuild.
"""
from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path

import pandas as pd


class SessionCalendar:
    def __init__(self, document):
        self.start, self.end = document["coverage_start"], document["coverage_end"]
        if pd.Timestamp(self.start) > pd.Timestamp(self.end):
            raise ValueError("calendar coverage range is reversed")
        self.sessions = {}
        for row in document["sessions"]:
            day = row["date"]
            if day in self.sessions or not self.start <= day <= self.end:
                raise ValueError("duplicate or out-of-coverage session")
            opening = pd.Timestamp(day + " " + row["open"], tz="America/New_York")
            closing = pd.Timestamp(day + " " + row["close"], tz="America/New_York")
            if opening >= closing or opening.minute % 15 or closing.minute % 15:
                raise ValueError("invalid session boundary")
            self.sessions[day] = (opening.tz_convert("UTC").tz_localize(None),
                                  closing.tz_convert("UTC").tz_localize(None))

    def bounds(self, day):
        day = str(day)
        if not self.start <= day <= self.end:
            raise ValueError(f"exchange calendar does not cover {day}; refresh the captured calendar")
        return self.sessions.get(day)

    def closed_starts(self, day, now):
        bounds = self.bounds(day)
        if bounds is None:
            return pd.DatetimeIndex([], name="timestamp")
        opening, closing = bounds
        cutoff = utc_naive(now)
        starts = pd.date_range(opening, closing, freq="15min", inclusive="left", name="timestamp")
        return starts[starts + pd.Timedelta(minutes=15) <= cutoff]

    def filter(self, frame, *, bar_minutes=15):
        if frame is None or frame.empty:
            return frame
        index = pd.DatetimeIndex(frame.index)
        if index.tz is not None:
            index = index.tz_convert("UTC").tz_localize(None)
        dates = index.tz_localize("UTC").tz_convert("America/New_York").strftime("%Y-%m-%d")
        keep = pd.Series(False, index=range(len(index)))
        for day in sorted(set(dates)):
            bounds = self.bounds(day)
            if bounds is not None:
                opening, closing = bounds
                keep |= (dates == day) & (index >= opening) & (index + pd.Timedelta(minutes=bar_minutes) <= closing)
        result = frame.iloc[keep.to_numpy()].copy()
        result.index = index[keep.to_numpy()]
        return result

    def scan_open(self, now):
        stamp = pd.Timestamp(now)
        if stamp.tz is None:
            raise ValueError("scan time requires timezone")
        day = stamp.tz_convert("America/New_York").strftime("%Y-%m-%d")
        bounds = self.bounds(day)
        if bounds is None:
            return False
        opening, closing = bounds
        # Preserve the experts' staggered final closed-bar passes through :03.
        return opening <= utc_naive(stamp) < closing + pd.Timedelta(minutes=4)


def utc_naive(value):
    stamp = pd.Timestamp(value)
    return stamp.tz_convert("UTC").tz_localize(None) if stamp.tz is not None else stamp


@lru_cache(maxsize=8)
def _read(path, modified_ns, size):
    return SessionCalendar(json.loads(Path(path).read_text()))


def configured_calendar():
    from nn_meta import config
    override = os.environ.get("NN_META_SESSION_CALENDAR")
    path = Path(override) if override else config.DATA_CACHE / "exchange_calendar.json"
    if not path.exists():
        if override or config.POOL == "v6" or getattr(config, "DATA_CANDIDATE", ""):
            raise ValueError("captured exchange calendar required; set NN_META_SESSION_CALENDAR")
        return None
    stat = path.stat()
    return _read(str(path), stat.st_mtime_ns, stat.st_size)
