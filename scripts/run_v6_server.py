"""Watch a frozen V6 release and consume sealed forward snapshots in isolation.

No notification switch exists here. A missing input producer is reported as
blocked, never as a successful model pass. This is the recording deployment.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path

from nn_meta.live.v6_release import FrozenGBT, read, sha, verify_release


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    tmp.replace(path)


def inspect_feed(path, now):
    if not path or not Path(path).exists():
        return {"status": "missing", "capture_complete": False}
    feed = read(path)
    stamp = datetime.fromisoformat(feed["ts"].replace("Z", "+00:00"))
    age = (now - stamp).total_seconds()
    return {"status": "fresh" if 0 <= age <= 120 else "stale",
            "heartbeat_age_seconds": age, "tick_recording": feed.get("tick_recording", False),
            "journal_errors": feed.get("journal_errors", 0),
            "recording_suspended": feed.get("recording_suspended", False),
            "quote_receipts": feed.get("received_quotes", 0),
            "trade_receipts": feed.get("trades", 0),
            "last_quote_received_ns": feed.get("last_quote_received_ns"),
            "contracts": feed.get("contracts", 0), "capture_complete": False}


def run(args, *, now=None):
    now = now or datetime.now(timezone.utc)
    args.state.mkdir(parents=True, exist_ok=True)
    with (args.state / ".runner.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        status = {"schema": "v6-server-status-v1", "checked_at": now.isoformat(),
                  "alerts_enabled": False, "scanner_promotion": False,
                  "live_decisions_verified": False, "delivered": 0}
        try:
            release = verify_release(args.release, args.anchor)
            status.update(campaign=release["campaign"], model_sha256=release["model_sha256"],
                          model_integrity="passed", members=40, features=164,
                          option_feed=inspect_feed(args.feed_heartbeat, now))
            if args.selftest:
                result = FrozenGBT(args.release, args.anchor).selftest()
                write(args.state / "selftest.json", {**result, "checked_at": now.isoformat()})
                status["selftest"] = result
            selftest = args.state / "selftest.json"
            tested = read(selftest) if selftest.exists() else {}
            if tested.get("status") != "passed" or tested.get("model_sha256") != release["model_sha256"]:
                raise ValueError("run and pass the release selftest on this host first")
            # The environment is set before importing the research scanner.
            os.environ.update(NN_META_POOL="v6", NN_META_CAMPAIGN=release["campaign"],
                NN_META_V6_EXPANDED="1", NN_META_V6_PARITY_POLICY="deferred",
                NN_META_V6_INPUTS=str(args.release / "training-inputs.json"),
                NN_META_V6_INPUTS_SHA256=release["training_inputs_sha256"])
            if not args.snapshot_index.exists():
                status.update(status="blocked", phase="awaiting_live_inputs",
                    blockers=["No sealed live snapshot producer is connected.",
                              "Full-universe pre-decision tick coverage is not established.",
                              "Forward portfolio allocation, exits and alert delivery need validation."],
                    next_input=str(args.snapshot_index))
            else:
                from nn_meta.session_calendar import configured_calendar
                calendar = configured_calendar()
                if calendar is None:
                    raise ValueError("a current exchange calendar is required before forward scoring")
                if not calendar.scan_open(now):
                    status.update(status="idle", phase="outside_market_hours")
                    write(args.state / "status.json", status)
                    print(json.dumps(status, sort_keys=True))
                    return status
                from nn_meta.live.v6_inputs import LiveSnapshot
                pointer = read(args.snapshot_index)
                snapshot_path = Path(pointer["path"])
                if not snapshot_path.is_absolute():
                    snapshot_path = args.snapshot_index.parent / snapshot_path
                snapshot = LiveSnapshot(snapshot_path, pointer["sha256"], now=now)
                snapshot.bind_training(os.environ["NN_META_V6_INPUTS"], release["training_inputs_sha256"])
                spec = read(args.release / "baseline_spec.json")
                if set(snapshot.bars.symbol) != set(spec["symbols"]):
                    raise ValueError("snapshot does not cover the frozen model universe")
                from nn_meta.live.v4_scan import scan_pass
                from nn_meta.live.v6_shadow import canonical
                import hashlib
                model = FrozenGBT(args.release, args.anchor)
                scope = {"schema": "v6-shadow-scope-v1", "bundle": model.config,
                    "artifacts": read(args.release / "model/manifest.json")["output_artifacts"],
                    "baseline_sha256": hashlib.sha256(canonical(spec).encode()).hexdigest(),
                    "portfolio": release["portfolio"], "release_sha256": args.anchor,
                    "sources": {str(p.relative_to(Path(__file__).resolve().parents[1])): sha(p)
                        for p in [Path(__file__), Path(__file__).resolve().parents[1] / "nn_meta/live/v4_scan.py",
                                  Path(__file__).resolve().parents[1] / "nn_meta/live/v6_inputs.py"]},
                    "research_only": True}
                result = scan_pass(bundle=model, spec=spec, surface=snapshot.surface,
                    bar_loader=snapshot.bar_loader, notifier=None, now=now,
                    state_dir=args.state, workers=1, live_inputs=snapshot,
                    shadow=True, shadow_scope=scope)
                status.update(status="failed" if result["error_count"] else "recorded",
                              phase="shadow", scan=result)
                # Recording signals alone does not validate executable positions.
        except Exception as exc:
            status.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            write(args.state / "status.json", status)
            raise
        write(args.state / "status.json", status)
        print(json.dumps(status, sort_keys=True))
        return status


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--release", type=Path, required=True)
    ap.add_argument("--anchor", required=True)
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--snapshot-index", type=Path, required=True)
    ap.add_argument("--feed-heartbeat", type=Path)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    args.release = args.release.absolute()
    args.state = args.state.absolute()
    args.snapshot_index = args.snapshot_index.absolute()
    run(args)
