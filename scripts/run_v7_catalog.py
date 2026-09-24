#!/usr/bin/env python3
"""Run the resumable V7 proposal catalog with a bounded CLI progress bar."""
from __future__ import annotations

import argparse
import concurrent.futures
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MINUTES = (5, 15, 30)


def stage_counts(output: Path, security_ids: list[str]) -> tuple[int, int, int, int, int]:
    features = proposals = feature_stores = complete_securities = 0
    for security_id in security_ids:
        security_done = True
        for minutes in MINUTES:
            base = output / security_id / str(minutes)
            feature_receipt = base / "features" / "summary" / "complete.json"
            proposal_receipt = base / "proposals" / "summary" / "complete.json"
            features += int((base / "features" / "declaration" / "complete.json").exists())
            features += int((base / "features" / "basis" / "complete.json").exists())
            feature_stores += int(feature_receipt.exists())
            proposals += int(proposal_receipt.exists())
            security_done &= proposal_receipt.exists()
        complete_securities += int(security_done)
    return features, feature_stores, proposals, len(security_ids) * len(MINUTES), complete_securities


def progress_line(features: int, feature_stores: int, proposals: int, total: int,
                  securities: int, total_securities: int) -> str:
    width = 32
    ratio = proposals / total if total else 1.0
    filled = min(width, int(ratio * width))
    bar = "#" * filled + "." * (width - filled)
    return (f"\033[2K\rCatalog [{bar}] proposals {proposals}/{total} | "
            f"features {features} receipts/{feature_stores} sealed | "
            f"securities {securities}/{total_securities}")


def emit_progress(message: str) -> None:
    """Render live in a TTY; preserve periodic snapshots in pipes/logs."""
    if sys.stdout.isatty():
        print(message, end="", flush=True)
    else:
        print(message.replace("\033[2K\r", ""), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--actions", type=Path, required=True)
    parser.add_argument("--action-coverage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, required=True,
                        help="Concurrent security builders; four is the bounded outer-worker ceiling.")
    parser.add_argument("--batch-columns", type=int, default=8)
    parser.add_argument("--working-bytes", type=int, default=128 * 1024**2)
    parser.add_argument("--compact-final", action="store_true",
                        help="Remove build-only signal matrices after each timeframe seals")
    parser.add_argument("--log-dir", type=Path,
                        help="Worker-log directory; defaults to a namespace derived from --output")
    parser.add_argument("--reuse-manifest", type=Path,
                        help="Verified proof for sealed securities built with equivalent earlier actions")
    parser.add_argument("--preflight-only", action="store_true",
                        help="Validate exact configured inputs and reuse proof, then exit before workers")
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("--workers must be between 1 and 4; four is the bounded outer-worker ceiling")
    if not args.output.resolve().is_relative_to(ROOT / "nn_meta"):
        parser.error("--output must be under nn_meta/")

    import pandas as pd
    from nn_meta.v7.catalog_reuse import check_admitted_actions, verify_reuse_manifest
    security_ids = sorted(pd.read_parquet(args.history / "history.parquet",
                                          columns=["security_id"])["security_id"].unique())
    gate = check_admitted_actions(args.history, args.actions, args.action_coverage)
    if gate["securities"] != len(security_ids):
        raise ValueError("Action preflight omitted catalog securities")
    reused = set()
    if args.reuse_manifest:
        proof = verify_reuse_manifest(args.reuse_manifest, output=args.output,
                                      actions=args.actions, coverage=args.action_coverage)
        reused = set(proof["securities"])
        if not reused.issubset(security_ids):
            raise ValueError("Reuse proof contains unknown securities")
    for security_id in reused:
        if not all((args.output / security_id / str(minutes) / "proposals/summary/complete.json").exists()
                   for minutes in MINUTES):
            raise ValueError("Reuse proof includes incomplete security")
    if args.preflight_only:
        print(json.dumps({"preflight": "passed", **gate,
                          "reused_securities": len(reused),
                          "remaining_builds": len(security_ids) - len(reused)}, sort_keys=True))
        return 0
    args.output.mkdir(parents=True, exist_ok=True)
    log_dir = args.log_dir or Path("/tmp") / f"{args.output.name}-logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    base = [sys.executable, str(ROOT / "scripts/build_v7_proposals.py"),
            "--source", str(args.source), "--history", str(args.history),
            "--actions", str(args.actions), "--action-coverage", str(args.action_coverage),
            "--output", str(args.output), "--workers", "1",
            "--batch-columns", str(args.batch_columns), "--working-bytes", str(args.working_bytes)]
    if args.compact_final:
        base.append("--compact-final")
    for minutes in MINUTES:
        base.extend(("--minutes", str(minutes)))

    def run_one(security_id: str) -> tuple[str, int]:
        log = (log_dir / f"{security_id}.log").open("a")
        try:
            result = subprocess.run(base + ["--security-id", security_id],
                                    cwd=ROOT, env={**os.environ, "PYTHONUNBUFFERED": "1",
                                                   "MPLCONFIGDIR": "/tmp/mpl-v7-full"},
                                    stdout=log, stderr=subprocess.STDOUT, check=False)
            return security_id, result.returncode
        finally:
            log.close()

    results: dict[str, int] = {}
    pending = iter(security_id for security_id in security_ids if security_id not in reused)
    lock_path = args.output / ".catalog-run.lock"
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("another V7 catalog runner is already active")
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(run_one, security_id): security_id
                       for security_id in [next(pending, None) for _ in range(args.workers)]
                       if security_id is not None}
            failed = False
            while futures:
                features, feature_stores, proposals, total, complete_securities = stage_counts(args.output, security_ids)
                emit_progress(progress_line(features, feature_stores, proposals, total,
                                            complete_securities, len(security_ids)))
                finished = [future for future in futures if future.done()]
                for future in finished:
                    security_id = futures.pop(future)
                    sid, rc = future.result()
                    results[sid] = rc
                    failed |= bool(rc)
                if not failed:
                    for _ in finished:
                        next_id = next(pending, None)
                        if next_id is not None:
                            futures[pool.submit(run_one, next_id)] = next_id
                if futures:
                    time.sleep(5)
    features, feature_stores, done, total, complete_securities = stage_counts(args.output, security_ids)
    failures = {sid: rc for sid, rc in results.items() if rc}
    emit_progress(progress_line(features, feature_stores, done, total, complete_securities, len(security_ids)))
    print(json.dumps({"security_ids": len(security_ids), "complete_timeframes": done,
                      "target_timeframes": total, "complete_securities": complete_securities,
                      "failed_builders": failures, "reused_securities": len(reused),
                      "research_ready": False}, sort_keys=True))
    return 1 if failures or done != total else 0


if __name__ == "__main__":
    raise SystemExit(main())
