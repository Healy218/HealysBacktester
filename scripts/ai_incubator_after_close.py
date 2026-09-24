#!/usr/bin/env python3
"""Run the read-only incubator campaign after market close.

This entrypoint is safe to schedule, but production activation remains an
explicit deployment decision: execution is disabled unless the caller opts in.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from incubator.budget import ResourceBudget
from incubator.after_close import DailyInputError, capture_v6_day, load_feature_request
from incubator.campaign import run_campaign
from incubator.forward import load_v6_snapshot
from incubator.receipts import write_json_atomic
from incubator.registry import discover


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--v6-index", type=Path, required=True)
    parser.add_argument("--v6-candidates-root", type=Path, required=True)
    parser.add_argument("--v6-model-config", type=Path, required=True)
    parser.add_argument("--v6-feature-dir", type=Path,
                        help="Explicit sealed V6 matrix, including a matured outcome join, for replay.")
    parser.add_argument("--feature-root", type=Path, required=True)
    parser.add_argument("--v5-feature-dir", type=Path,
                        help="Separately captured, sealed V5 paper features; never substitute V6 candidates.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--campaign-seconds", type=float, default=3600.0)
    parser.add_argument("--artifact-seconds", type=int, default=120)
    parser.add_argument("--memory-bytes", type=int, default=2 * 1024**3)
    parser.add_argument("--output-bytes", type=int, default=16 * 1024**2)
    parser.add_argument("--max-artifacts", type=int, default=64)
    parser.add_argument("--allow-execution", action="store_true",
                        help="Explicitly opt into sandbox entrypoints; default is verification-only.")
    args = parser.parse_args()
    cutoff = args.as_of or datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    snapshot = load_v6_snapshot(args.v6_index)
    if snapshot.through > cutoff:
        raise ValueError("V6 data index is newer than the requested close date")
    entries = discover([args.bundle_root])
    run_id = args.run_id or f"close-{cutoff.replace('-', '')}"
    run_dir = args.output_dir / run_id
    requests = {}
    blocked = []
    for generation in ("v5", "v6"):
        generation_entries = [entry for entry in entries
                              if entry["artifact_id"].startswith((f"incubator-{generation}-", f"{generation}-"))]
        if not generation_entries:
            continue
        try:
            if generation == "v6":
                feature_dir = (args.v6_feature_dir or
                               capture_v6_day(args.v6_candidates_root, args.v6_model_config,
                                              args.feature_root, cutoff))
            else:
                if args.v5_feature_dir is None:
                    raise DailyInputError("v5: genuine sealed V5 paper feature capture is not configured")
                feature_dir = args.v5_feature_dir
            selected = load_feature_request(feature_dir, generation=generation, as_of=cutoff)
            for entry in generation_entries:
                requests[entry["artifact_id"]] = {**selected, "artifact_id": entry["artifact_id"]}
        except (DailyInputError, OSError, ValueError) as exc:
            blocked.extend({"artifact_id": entry["artifact_id"], "reason": str(exc)}
                           for entry in generation_entries)
    unknown = [entry for entry in entries if entry["artifact_id"] not in requests
               and not any(item["artifact_id"] == entry["artifact_id"] for item in blocked)]
    blocked.extend({"artifact_id": entry["artifact_id"], "reason": "unknown generation; no input route"}
                   for entry in unknown)
    selected_entries = [entry for entry in entries if entry["artifact_id"] in requests]
    budget = ResourceBudget(campaign_seconds=args.campaign_seconds,
                            artifact_seconds=args.artifact_seconds,
                            memory_bytes=args.memory_bytes,
                            output_bytes=args.output_bytes,
                            max_artifacts=args.max_artifacts)
    if selected_entries:
        summary = run_campaign(selected_entries, request={"as_of": cutoff}, output_dir=run_dir,
                               run_id=run_id, checkpoint_path=run_dir / "checkpoint.json",
                               artifact_requests=requests,
                               allow_execution=args.allow_execution, budget=budget)
    else:
        summary = {"schema": "incubator-campaign-v1", "run_id": run_id,
                   "artifact_count": 0, "completed_count": 0, "failed_count": 0,
                   "receipts": [], "read_only": True}
    summary["input_blocked"] = blocked
    summary["input_blocked_count"] = len(blocked)
    summary["v6_snapshot_through"] = snapshot.through
    summary["as_of"] = cutoff
    performance = {
        "schema": "incubator-performance-log-v1", "run_id": run_id, "as_of": cutoff,
        "read_only": True,
        "artifacts": [
            {"artifact_id": receipt["artifact_id"], "status": receipt["status"],
             "output_dir": receipt.get("output_dir"),
             "prediction_count": receipt.get("sandbox", {}).get("prediction_count"),
             "metrics": receipt.get("sandbox", {}).get("metrics")}
            for receipt in summary["receipts"]
        ],
        "input_blocked": blocked,
    }
    write_json_atomic(run_dir / "performance-log.json", performance)
    write_json_atomic(run_dir / "after-close-summary.json", summary)
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0 if summary["failed_count"] == 0 and not blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
