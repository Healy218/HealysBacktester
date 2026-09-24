"""Capture finite, reviewed V7 ticker spans under the shared acquisition cap."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import fcntl
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from nn_meta.v7.storage import sha
    from scripts.download_v7_data import acquire, save

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base, output = args.base.resolve(), args.output.resolve()
    if output.parent != base.parent or not (output.parent / "quota.json").is_file():
        raise ValueError("Existing shared acquisition quota required")
    calendar = json.loads((base / "calendar.json").read_text())
    sessions = {row["date"] for row in calendar["sessions"]}
    requests = json.loads(args.requests.read_text())
    if not isinstance(requests, list) or not 0 < len(requests) <= 100:
        raise ValueError("Finite nonempty ticker span requests required")
    tasks, seen = [], set()
    for row in requests:
        if (set(row) != {"symbol", "start", "end", "feed"}
                or not re.fullmatch(r"[A-Z][A-Z0-9.]{0,14}", row["symbol"])
                or row["feed"] not in {"sip", "otc"}
                or row["start"] not in sessions or row["end"] not in sessions
                or row["start"] > row["end"]):
            raise ValueError("Invalid reviewed ticker span")
        start, end = date.fromisoformat(row["start"]), date.fromisoformat(row["end"])
        for year in range(start.year, end.year + 1):
            left = max(start, date(year, 1, 1))
            right = min(end, date(year, 12, 31))
            key = row["symbol"], year
            if key in seen:
                raise ValueError("Overlapping ticker/year requests")
            seen.add(key)
            for adjustment in ("raw", "all"):
                tasks.append({"kind": "stock", "symbol": row["symbol"],
                              "adjustment": adjustment, "feed": row["feed"],
                              "start": left.isoformat() + "T00:00:00Z",
                              "end": (right + timedelta(days=1)).isoformat() + "T00:00:00Z",
                              "key": f"stock_1m/{adjustment}/{row['symbol']}/{year}"})
    scope = {"schema": "v7-reviewed-alias-span-capture-v1", "requests": requests,
             "requests_sha256": sha(args.requests),
             "sources": {str(Path(__file__)): sha(Path(__file__)),
                         str(ROOT / "scripts/download_v7_data.py"):
                             sha(ROOT / "scripts/download_v7_data.py")},
             "calendar_sha256": sha(base / "calendar.json"),
             "research_ready": False}
    output.mkdir(parents=True, exist_ok=True)
    with (output.parent / ".acquisition.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt_path = output / "acquisition.json"
        if receipt_path.exists() and json.loads(receipt_path.read_text()) != scope:
            raise ValueError("Capture scope changed; use a fresh output")
        save(receipt_path, scope)
        state = {"total": len(tasks), "completed": 0, "failed": 0,
                 "research_ready": False}
        for task in tasks:
            if any(sha(path) != digest for path, digest in scope["sources"].items()):
                raise ValueError("Capture implementation changed")
            try:
                result = acquire(str(output), task, 100)
                state["completed"] += 1
            except Exception as exc:
                state["failed"] += 1
                result = {"key": task["key"], "error_type": type(exc).__name__,
                          "reason": str(exc)}
            print(json.dumps(result), flush=True)
            save(output / "status.json", state)
            if state["failed"]:
                raise RuntimeError("Reviewed alias capture incomplete")


if __name__ == "__main__":
    main()
