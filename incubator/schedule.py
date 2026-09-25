"""Choose the last fully closed exchange session from the deployed calendar."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo


def last_closed_session(index_path: Path, *, now: datetime | None = None,
                        lag_minutes: int = 30) -> str:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or lag_minutes < 0:
        raise ValueError("session selection requires an aware clock and nonnegative lag")
    index = json.loads(Path(index_path).read_text())
    calendar = json.loads((Path(index["path"]) / "calendar.json").read_text())
    zone = ZoneInfo("America/New_York")
    current = now.astimezone(zone)
    eligible = []
    for row in calendar["sessions"]:
        closed = datetime.combine(date.fromisoformat(row["date"]),
                                  time.fromisoformat(row["close"]), tzinfo=zone)
        if closed + timedelta(minutes=lag_minutes) <= current:
            eligible.append(row["date"])
    if not eligible:
        raise ValueError("exchange calendar has no fully closed covered session")
    return max(eligible)
