from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from incubator.schedule import last_closed_session


def test_last_closed_session_handles_after_midnight_and_weekend(tmp_path: Path) -> None:
    (tmp_path / "calendar.json").write_text(json.dumps({"sessions": [
        {"date": "2026-09-24", "open": "09:30", "close": "16:00"},
        {"date": "2026-09-25", "open": "09:30", "close": "16:00"}]}))
    index = tmp_path / "data-index.json"
    index.write_text(json.dumps({"path": str(tmp_path)}))
    assert last_closed_session(index, now=datetime(2026, 9, 25, 4, 15, tzinfo=timezone.utc)) == "2026-09-24"
    assert last_closed_session(index, now=datetime(2026, 9, 25, 20, 29, tzinfo=timezone.utc)) == "2026-09-24"
    assert last_closed_session(index, now=datetime(2026, 9, 25, 20, 30, tzinfo=timezone.utc)) == "2026-09-25"
    assert last_closed_session(index, now=datetime(2026, 9, 26, 16, 0, tzinfo=timezone.utc)) == "2026-09-25"
