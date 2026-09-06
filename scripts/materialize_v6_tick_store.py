"""Materialize the existing tick-store contract with one raw bundle resident.

The task must bind this implementation as a reference. All raw bytes and
exact coverage are verified; only memory usage differs from the small-pilot
materializer. No overlapping bundles are silently stitched or preferred.
"""
import json
from pathlib import Path

import pandas as pd

from nn_meta import option_tick_dataset as d
from options.data.massive_ticks import TickDataError, canonical_bytes


def materialize(task, capture_directories, output_dir):
    d._verify_task(task)
    own = Path(__file__).resolve()
    source_hash = d._file_hash(own)
    if not any(ref["sha256"] == source_hash for ref in task["selection_references"]):
        raise TickDataError("streaming materializer source must be bound in task references")
    output = d._path(output_dir)
    directories = [d._path(p) for p in capture_directories]
    if output.exists() or len(set(directories)) != len(directories):
        raise TickDataError("fresh output and distinct capture directories required")
    if any(output.is_relative_to(p) for p in directories):
        raise TickDataError("feature output cannot modify raw captures")
    identities, reports, by_contract = [], [], {}
    for number, directory in enumerate(directories):
        report = json.loads((directory / "manifest.json").read_bytes())
        identity = d._capture_identity(directory, report)
        d._verify_capture_identity(identity)
        identities.append(identity)
        reports.append(report)
        for contract in report["plan"]["contracts"]:
            by_contract.setdefault(contract, []).append(number)
    assignments, rows, coverage = {}, {}, {}
    for req in task["requests"]:
        rid = req["request_id"]
        if req["status"] == "unselected":
            rows[rid] = {"request_id": rid, **{k: req[k] for k in d.KEY_COLUMNS},
                "option_tick_status": "unselected", **dict.fromkeys((*d.NUMERIC_FEATURES, *d.AUDIT_COLUMNS))}
            continue
        matches = [n for n in by_contract.get(req["contract"], [])
            if reports[n]["plan"]["start_ns"] <= req["window_start_ns"]
            and req["window_end_ns"] <= reports[n]["plan"]["end_ns"]]
        if len(matches) != 1:
            raise TickDataError("required window has missing or ambiguous verified capture coverage: " + rid)
        assignments.setdefault(matches[0], []).append(req)
    policy = task["feature_policy"]
    for number, directory in enumerate(directories):
        report, captures = d.load_verified_capture(directory)
        identity = identities[number]
        if d._capture_identity(directory, report) != identity:
            raise TickDataError("raw bundle changed during materialization")
        entries = {entry["contract"]: entry for entry in report["contracts"]}
        computed = {}
        for req in assignments.get(number, []):
            contract = req["contract"]
            key = (contract, req["window_start_ns"], req["window_end_ns"])
            if key not in computed:
                data, entry = captures[contract], entries[contract]
                kwargs = {"start_ns": req["window_start_ns"], "end_ns": req["window_end_ns"],
                    "max_quote_age_ns": policy["max_quote_age_ns"],
                    "allowed_trade_conditions": policy["allowed_trade_conditions"],
                    "allow_unconditioned_trades": False}
                reported = d.verified_window_features(data["quotes"], data["trades"],
                    quote_manifest=entry["captures"]["quotes"], trade_manifest=entry["captures"]["trades"],
                    contract=contract, **kwargs)
                allowed = set(policy["allowed_trade_conditions"])
                eligible = d.window_features(data["quotes"],
                    [row for row in data["trades"] if d._eligible_trade(row, allowed)], complete=True,
                    coverage_start_ns=report["plan"]["start_ns"], coverage_end_ns=report["plan"]["end_ns"], **kwargs)
                computed[key] = reported, eligible
            reported, eligible = computed[key]
            rows[req["request_id"]] = d.compute_feature_row(reported, req, eligible=eligible)
            coverage[req["request_id"]] = {"capture_manifest_sha256": identity["files_sha256"]["manifest.json"],
                "directory": identity["directory"], "contract": contract,
                "start_ns": req["window_start_ns"], "end_ns": req["window_end_ns"]}
        data = None
        del captures, computed
    ordered = [rows[r["request_id"]] for r in task["requests"]]
    frame = pd.DataFrame(ordered, columns=d.TABLE_COLUMNS)
    for col in d.KEY_COLUMNS[2:]:
        frame[col] = pd.array([row[col] for row in ordered], dtype="int64")
    for col in d.NUMERIC_FEATURES:
        frame[col] = pd.array([row[col] for row in ordered], dtype="Float64")
    output.mkdir(parents=True, exist_ok=False)
    task_path, rows_path = output / "task.json", output / "features.parquet"
    task_path.write_bytes(canonical_bytes(task) + b"\n")
    frame.to_parquet(rows_path, index=False)
    for identity in identities:
        d._verify_capture_identity(identity)
    d._verify_task(task)
    if d._file_hash(own) != source_hash:
        raise TickDataError("streaming materializer changed during execution")
    manifest = {"schema": d.SCHEMA, "complete": True, "task_sha256": task["task_sha256"],
        "task_file_sha256": d._file_hash(task_path), "features_sha256": d._file_hash(rows_path),
        "numeric_features": list(d.NUMERIC_FEATURES), "row_count": len(ordered),
        "selected_request_count": len(coverage), "unselected_request_count": len(ordered) - len(coverage),
        "coverage": coverage, "captures": identities, "implementation": task["implementation"],
        "feature_policy": policy, "model_admission": False}
    manifest["store_sha256"] = d._hash(manifest)
    (output / "manifest.json").write_bytes(canonical_bytes(manifest) + b"\n")
    return manifest
