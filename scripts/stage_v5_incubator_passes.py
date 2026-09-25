#!/usr/bin/env python3
"""Stage and verify one completed V5 scanner day from the server."""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from incubator.v5_features import assemble_v5_day
from incubator.schedule import last_closed_session


def _check_session_bars(day: Path, as_of: str, calendar_index: Path) -> None:
    index = json.loads(Path(calendar_index).read_text())
    calendar = json.loads((Path(index["path"]) / "calendar.json").read_text())
    matches = [row for row in calendar["sessions"] if row["date"] == as_of]
    if len(matches) != 1:
        raise ValueError(f"no unique covered exchange session for {as_of}")
    session = matches[0]
    market_date = date.fromisoformat(as_of)
    zone = ZoneInfo("America/New_York")
    opened = datetime.combine(market_date, time.fromisoformat(session["open"]), tzinfo=zone)
    closed = datetime.combine(market_date, time.fromisoformat(session["close"]), tzinfo=zone)
    expected = set()
    cursor = opened
    while cursor < closed:
        expected.add(cursor.astimezone(timezone.utc).isoformat())
        cursor += timedelta(minutes=15)
    actual = {json.loads(path.read_text())["signal_bar"]
              for path in day.glob("*/feature-manifest.json")}
    if actual != expected:
        raise ValueError(f"V5 session incomplete: {len(actual)}/{len(expected)} bars for {as_of}")


def stage_day(*, as_of: str, destination: Path, model_config: Path,
              remote: str, remote_root: str, calendar_index: Path | None = None) -> dict:
    date.fromisoformat(as_of)
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+", remote):
        raise ValueError("remote must be a single SSH host")
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", remote_root):
        raise ValueError("remote root must be an absolute plain path")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / as_of
    config = json.loads(Path(model_config).read_text())
    if target.exists():
        with tempfile.TemporaryDirectory(prefix="v5-stage-check-", dir=destination) as temporary:
            result = assemble_v5_day(destination, Path(temporary) / "assembled", config, through=as_of)
        if calendar_index is not None:
            _check_session_bars(target, as_of, calendar_index)
        return {"through": as_of, "passes": len(result["sources"]), "rows": result["rows"],
                "status": "already_staged_and_verified"}
    with tempfile.TemporaryDirectory(prefix="v5-stage-", dir=destination) as temporary:
        temporary_root = Path(temporary)
        day = temporary_root / as_of
        day.mkdir()
        subprocess.run(["rsync", "-a", "-e", "ssh -o BatchMode=yes", "--",
                        f"{remote}:{remote_root.rstrip('/')}/{as_of}/", str(day) + "/"],
                       check=True, timeout=180)
        result = assemble_v5_day(temporary_root, temporary_root / "assembled", config, through=as_of)
        if calendar_index is not None:
            _check_session_bars(day, as_of, calendar_index)
        day.replace(target)
    return {"through": as_of, "passes": len(result["sources"]), "rows": result["rows"],
            "status": "staged_and_verified"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--destination", type=Path, default=ROOT / "incubator/artifacts/v5-passes")
    parser.add_argument("--model-config", type=Path, default=ROOT / "nn_meta/model_final_v5/ensemble_config.json")
    parser.add_argument("--calendar-index", type=Path,
                        help="V6 data index containing the dated exchange calendar")
    parser.add_argument("--remote", default="mrhea@62.238.20.66")
    parser.add_argument("--remote-root", default="/home/mrhea/HealysBacktester/incubator/artifacts/v5-passes")
    args = parser.parse_args()
    selected = args.as_of or os.environ.get("AI_INCUBATOR_AS_OF") or (
        last_closed_session(args.calendar_index) if args.calendar_index else
        datetime.now(ZoneInfo("America/New_York")).date().isoformat())
    print(json.dumps(stage_day(as_of=selected, destination=args.destination,
        model_config=args.model_config, remote=args.remote, remote_root=args.remote_root,
        calendar_index=args.calendar_index), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
