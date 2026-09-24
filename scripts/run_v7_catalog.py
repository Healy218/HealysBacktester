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


def preflight_loader(payload: dict) -> dict:
    """Return a compact result from the production loader, never raw frames."""
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from scripts.build_v7_proposals import load_inputs
    sid = payload["security_id"]
    try:
        raw, actions, _, _, routing, _, declaration = load_inputs(payload)
        return dict(security_id=sid, status="passed", raw_minutes=len(raw),
                    routed_days=len(routing), actions=len(actions),
                    coverage_receipt=declaration["receipt_sha256"])
    except Exception as exc:
        return dict(security_id=sid, status="failed", error_type=type(exc).__name__,
                    reason=str(exc))


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
    parser.add_argument("--supplemental-coverage", type=Path,
                        help="Reviewed coverage for securities whose admission differs from the base")
    parser.add_argument("--previous-supplemental-coverage", type=Path,
                        help="Previously sealed supplemental receipt; reuse only exact per-security equivalent panels")
    parser.add_argument("--defer-unadmitted", action="store_true",
                        help="Build admitted securities and report zero-admission securities as unfinished")
    parser.add_argument("--preflight-only", action="store_true",
                        help="Validate exact configured inputs and reuse proof, then exit before workers")
    parser.add_argument("--loader-preflight", action="store_true",
                        help="Run the real proposal loader for every unfinished security before workers")
    parser.add_argument("--loader-preflight-report", type=Path,
                        help="Store the exact compact real-loader results under nn_meta")
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("--workers must be between 1 and 4; four is the bounded outer-worker ceiling")
    if not args.output.resolve().is_relative_to(ROOT / "nn_meta"):
        parser.error("--output must be under nn_meta/")
    if args.loader_preflight_report and not args.loader_preflight_report.resolve().is_relative_to(ROOT / "nn_meta"):
        parser.error("--loader-preflight-report must be under nn_meta/")

    import pandas as pd
    from nn_meta.v7.catalog_reuse import (
        actions_by_security, check_admitted_actions, current_source_hashes,
        declared_actions, source_compatible, verify_reuse_manifest,
    )
    from nn_meta.v7.catalog_audit import audit_store, expected_variants
    from nn_meta.v7.storage import sha, verify
    security_ids = sorted(pd.read_parquet(args.history / "history.parquet",
                                          columns=["security_id"])["security_id"].unique())
    verify(args.action_coverage)
    if args.supplemental_coverage:
        verify(args.supplemental_coverage)
    gate = check_admitted_actions(args.history, args.actions, args.action_coverage)
    if gate["securities"] != len(security_ids):
        raise ValueError("Action preflight omitted catalog securities")
    keys = ["security_id", "source_date"]
    coverage_columns = keys + ["coverage_status", "history_admitted", "event_id", "identity_event_id"]
    base_coverage = pd.read_parquet(args.action_coverage / "coverage.parquet",
                                    columns=coverage_columns)
    alternate_ids: set[str] = set()
    alternate_coverage = None
    previous_sha = None
    previous_panels: dict[str, pd.DataFrame] = {}
    if args.previous_supplemental_coverage:
        if not args.supplemental_coverage:
            raise ValueError("Previous supplemental coverage requires the current supplemental coverage")
        verify(args.previous_supplemental_coverage)
        previous_sha = sha(args.previous_supplemental_coverage / "complete.json")
        if sha(args.previous_supplemental_coverage / "policy.json") != sha(
                args.supplemental_coverage / "policy.json"):
            raise ValueError("Supplemental coverage policy differs")
    if args.supplemental_coverage:
        alternate_gate = check_admitted_actions(args.history, args.actions,
                                                args.supplemental_coverage)
        if alternate_gate["securities"] != len(security_ids):
            raise ValueError("Supplemental coverage omits catalog securities")
        alternate_coverage = pd.read_parquet(args.supplemental_coverage / "coverage.parquet",
                                             columns=coverage_columns)
        if (len(base_coverage) != len(alternate_coverage)
                or base_coverage.duplicated(keys).any()
                or alternate_coverage.duplicated(keys).any()):
            raise ValueError("Coverage panels must have the same unique sessions")
        comparison = base_coverage.merge(alternate_coverage, on=keys,
                                         suffixes=("_base", "_supplemental"), validate="one_to_one")
        if len(comparison) != len(base_coverage):
            raise ValueError("Supplemental coverage changes catalog sessions")
        changed = pd.Series(False, index=comparison.index)
        for name in coverage_columns[2:]:
            changed |= (comparison[name + "_base"].fillna("") !=
                        comparison[name + "_supplemental"].fillna(""))
        alternate_ids = set(comparison.loc[changed, "security_id"])
    selected_coverage = base_coverage if alternate_coverage is None else pd.concat([
        base_coverage[~base_coverage.security_id.isin(alternate_ids)],
        alternate_coverage[alternate_coverage.security_id.isin(alternate_ids)]],
        ignore_index=True)
    observed = pd.read_parquet(args.history / "history.parquet",
                               columns=["security_id", "source_date", "source_status"])
    observed = observed[observed.source_status.eq("observed")]
    admitted_observed = observed.merge(
        selected_coverage[keys + ["history_admitted"]],
        on=keys, how="left", validate="one_to_one")
    if admitted_observed.history_admitted.isna().any():
        raise ValueError("Coverage omits observed history")
    unadmitted_ids = set(security_ids) - set(admitted_observed.loc[
        admitted_observed.history_admitted.astype(bool), "security_id"])
    if unadmitted_ids and not args.defer_unadmitted:
        raise ValueError(f"{len(unadmitted_ids)} securities have no admitted observed history")
    reused = set()
    if args.reuse_manifest:
        proof = verify_reuse_manifest(args.reuse_manifest, output=args.output,
                                      actions=args.actions, coverage=args.action_coverage)
        reused = set(proof["securities"])
        if not reused.issubset(security_ids):
            raise ValueError("Reuse proof contains unknown securities")
        if reused & alternate_ids:
            raise ValueError("Supplemental coverage changes a reused security")
    for security_id in reused:
        if not all((args.output / security_id / str(minutes) / "proposals/summary/complete.json").exists()
                   for minutes in MINUTES):
            raise ValueError("Reuse proof includes incomplete security")
    # Securities sealed by an earlier controller after its first failure are
    # independently verified before they are skipped on resume.
    newly_sealed = set()
    grouped_actions = actions_by_security(args.actions)
    current_sources = current_source_hashes()
    variants = expected_variants()
    for security_id in set(security_ids) - reused:
        if not all((args.output / security_id / str(minutes) / "proposals/summary/complete.json").exists()
                   for minutes in MINUTES):
            continue
        coverage_path = (args.supplemental_coverage if security_id in alternate_ids
                         else args.action_coverage)
        coverage_sha = sha(coverage_path / "complete.json")
        prior_equivalent = False
        for minutes in MINUTES:
            base = args.output / security_id / str(minutes)
            declaration = json.loads((base / "features/declaration/declaration.json").read_text())
            declared = declared_actions(grouped_actions.get(security_id, []),
                                        declaration["start"], declaration["end"])
            canonical = lambda rows: sorted(json.dumps(row, sort_keys=True) for row in rows)
            bound_coverage = declaration.get("action_coverage", {}).get("receipt_sha256")
            if bound_coverage != coverage_sha and previous_sha and bound_coverage == previous_sha:
                if security_id not in previous_panels:
                    old = pd.read_parquet(args.previous_supplemental_coverage / "coverage.parquet",
                                          filters=[("security_id", "=", security_id)])
                    new = pd.read_parquet(coverage_path / "coverage.parquet",
                                          filters=[("security_id", "=", security_id)])
                    previous_panels[security_id] = old.sort_values("source_date").reset_index(drop=True)
                    prior_equivalent = (previous_panels[security_id].equals(
                        new.sort_values("source_date").reset_index(drop=True)))
                else:
                    new = pd.read_parquet(coverage_path / "coverage.parquet",
                                          filters=[("security_id", "=", security_id)])
                    prior_equivalent = previous_panels[security_id].equals(
                        new.sort_values("source_date").reset_index(drop=True))
            if (bound_coverage != coverage_sha and not prior_equivalent
                    or not source_compatible(declaration.get("sources", {}), current_sources)
                    or canonical(declaration.get("actions", [])) != canonical(declared)):
                raise ValueError(f"Sealed security differs from current inputs: {security_id}")
            audit_store(base, security_id=security_id, minutes=minutes,
                        variants=variants[minutes])
        newly_sealed.add(security_id)
    pending_ids = sorted(set(security_ids) - reused - newly_sealed - unadmitted_ids)
    loader_results = []
    if args.loader_preflight:
        from nn_meta.v7.scope import HISTORY_START, HISTORY_END
        payloads = [dict(source=args.source, history=args.history, actions=args.actions,
                         action_coverage=(args.supplemental_coverage if sid in alternate_ids
                                          else args.action_coverage),
                         active=ROOT / "docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json",
                         raw_supplement=[], start=HISTORY_START, end=HISTORY_END,
                         security_id=sid) for sid in pending_ids]
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            for completed, result in enumerate(pool.map(preflight_loader, payloads), 1):
                loader_results.append(result)
                if completed % 20 == 0 or completed == len(payloads):
                    print(json.dumps(dict(loader_preflight_completed=completed,
                                          loader_preflight_total=len(payloads),
                                          failures=sum(row["status"] == "failed"
                                                       for row in loader_results))), flush=True)
        report = dict(schema="v7-catalog-real-loader-preflight-v1", total=len(pending_ids),
                      passed=sum(row["status"] == "passed" for row in loader_results),
                      actions_sha256=sha(args.actions / "actions.json"),
                      base_coverage_sha256=sha(args.action_coverage / "complete.json"),
                      supplemental_coverage_sha256=(sha(args.supplemental_coverage / "complete.json")
                                                   if args.supplemental_coverage else None),
                      results=loader_results, research_ready=False)
        if args.loader_preflight_report:
            args.loader_preflight_report.parent.mkdir(parents=True, exist_ok=True)
            args.loader_preflight_report.write_text(json.dumps(report, indent=2) + "\n")
        if report["passed"] != report["total"]:
            failures = {row["security_id"]: row["reason"] for row in loader_results
                        if row["status"] == "failed"}
            raise ValueError(f"Real loader preflight failed for {len(failures)} securities: {failures}")
    if args.preflight_only:
        print(json.dumps({"preflight": "passed", **gate,
                          "reused_securities": len(reused),
                          "remaining_builds": len(pending_ids),
                          "real_loader_preflight_passed": len(loader_results) if args.loader_preflight else None,
                          "verified_newly_sealed": len(newly_sealed),
                          "verified_prior_supplemental_equivalent": sum(
                              sid in previous_panels for sid in newly_sealed),
                          "supplemental_securities": sorted(alternate_ids),
                          "deferred_unadmitted": sorted(unadmitted_ids)}, sort_keys=True))
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
            command = base + ["--security-id", security_id]
            if security_id in alternate_ids:
                i = command.index("--action-coverage")
                command[i + 1] = str(args.supplemental_coverage)
            result = subprocess.run(command,
                                    cwd=ROOT, env={**os.environ, "PYTHONUNBUFFERED": "1",
                                                   "MPLCONFIGDIR": "/tmp/mpl-v7-full"},
                                    stdout=log, stderr=subprocess.STDOUT, check=False)
            return security_id, result.returncode
        finally:
            log.close()

    results: dict[str, int] = {}
    pending = iter(security_id for security_id in security_ids
                   if security_id not in reused and security_id not in newly_sealed
                   and security_id not in unadmitted_ids)
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
                      "verified_newly_sealed": len(newly_sealed),
                      "deferred_unadmitted": sorted(unadmitted_ids),
                      "research_ready": False}, sort_keys=True))
    return 1 if failures or unadmitted_ids or done != total else 0


if __name__ == "__main__":
    raise SystemExit(main())
