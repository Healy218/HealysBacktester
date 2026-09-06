"""Prepare reviewed tick requests or ingest existing captures, entirely offline.

Both commands preview by default. --run only writes local immutable artifacts;
this module has no downloader, credential loading, or network execution path.
The requests must come from a separately reviewed decision-time selector.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

from nn_meta import option_tick_dataset as dataset
from options.data.massive_ticks import TickDataError, canonical_bytes

PLAN_SCHEMA = "option-tick-preparation-v1"


def _json(path):
    path = dataset._path(path)
    before = dataset._file_hash(path)
    value = json.loads(path.read_bytes())
    if dataset._file_hash(path) != before:
        raise TickDataError("JSON input changed while reading")
    return value


def _fresh(path):
    path = dataset._path(path)
    if path.exists():
        raise TickDataError("output must be a fresh immutable directory")
    return path


def capture_plan(task, *, max_span_ns=dataset.MAX_CAPTURE_NS, max_gap_ns=0):
    """Group identical bounds into provider-sized batches; do not download."""
    windows = dataset.plan_capture_windows(task, max_span_ns=max_span_ns, max_gap_ns=max_gap_ns)
    grouped = defaultdict(list)
    for window in windows:
        grouped[window["start_ns"], window["end_ns"]].append(window["contract"])
    batches = []
    for (start, end), contracts in sorted(grouped.items()):
        for offset in range(0, len(contracts), 10):
            batches.append({"contracts": sorted(contracts[offset:offset + 10]),
                            "start_ns": start, "end_ns": end})
    result = {"schema": PLAN_SCHEMA, "task_sha256": task["task_sha256"],
              "max_span_ns": max_span_ns, "max_gap_ns": max_gap_ns,
              "request_count": len(task["requests"]),
              "selected_request_count": sum(r["status"] == "selected" for r in task["requests"]),
              "windows": windows, "capture_batches": batches,
              "downloads_started": False, "model_admission": False}
    result["plan_sha256"] = dataset._hash(result)
    return result


def prepare(args):
    output = _fresh(args.output)
    requests = _json(args.requests)
    if not isinstance(requests, list) or not requests:
        raise TickDataError("requests JSON must contain a nonempty explicit request list")
    policy = _json(args.policy)
    references = list(dict.fromkeys([*args.selection_reference, args.requests, args.policy,
                                    *([args.root_aliases] if args.root_aliases else [])]))
    aliases = _json(args.root_aliases) if args.root_aliases else None
    if aliases is not None and not isinstance(aliases, dict):
        raise TickDataError("root aliases JSON must be an object")
    task = dataset.create_task_manifest(requests, selection_reference_paths=references,
        feature_policy=policy, root_aliases=aliases)
    plan = capture_plan(task, max_span_ns=args.max_span_ns, max_gap_ns=args.max_gap_ns)
    if args.run:
        output.mkdir(parents=True, exist_ok=False)
        task_path, plan_path = output / "task.json", output / "capture_plan.json"
        task_path.write_bytes(canonical_bytes(task) + b"\n")
        plan_path.write_bytes(canonical_bytes(plan) + b"\n")
        dataset.load_task_manifest(task_path, expected_task_sha256=task["task_sha256"])
        manifest = {"schema": PLAN_SCHEMA, "complete": True,
                    "task_sha256": task["task_sha256"], "plan_sha256": plan["plan_sha256"],
                    "files_sha256": {p.name: dataset._file_hash(p) for p in (task_path, plan_path)},
                    "downloads_started": False, "model_admission": False}
        (output / "manifest.json").write_bytes(canonical_bytes(manifest) + b"\n")
    return {"operation": "prepare", "written": args.run, "output": str(output),
            "task_sha256": task["task_sha256"], "capture_plan": plan}


def materialize(args):
    output = _fresh(args.output)
    task = dataset.load_task_manifest(args.task, expected_task_sha256=args.expected_task_sha256)
    captures = [dataset._path(p) for p in args.capture]
    if any(not p.is_dir() for p in captures) or len(set(captures)) != len(captures):
        raise TickDataError("captures must be distinct existing directories")
    result = {"operation": "materialize", "written": False, "output": str(output),
              "task_sha256": task["task_sha256"], "capture_directories": list(map(str, captures)),
              "capture_contents_verified": False, "downloads_started": False, "model_admission": False}
    if args.run:
        manifest = dataset.materialize_store(task, captures, output)
        dataset.load_feature_store(output, expected_task_sha256=task["task_sha256"],
                                   expected_store_sha256=manifest["store_sha256"])
        result.update(written=True, capture_contents_verified=True,
                      store_sha256=manifest["store_sha256"], row_count=manifest["row_count"])
    return result


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    prepare_ap = sub.add_parser("prepare", help="preview or write a bound task and capture plan")
    prepare_ap.add_argument("--requests", type=Path, required=True)
    prepare_ap.add_argument("--policy", type=Path, required=True,
                            help="JSON returned by nn_meta.option_tick_dataset.feature_policy")
    prepare_ap.add_argument("--selection-reference", type=Path, action="append", required=True)
    prepare_ap.add_argument("--root-aliases", type=Path)
    prepare_ap.add_argument("--max-span-ns", type=int, default=dataset.MAX_CAPTURE_NS)
    prepare_ap.add_argument("--max-gap-ns", type=int, default=0)
    prepare_ap.set_defaults(action=prepare)
    ingest_ap = sub.add_parser("materialize", help="preview or verify existing captures into a store")
    ingest_ap.add_argument("--task", type=Path, required=True)
    ingest_ap.add_argument("--expected-task-sha256", required=True)
    ingest_ap.add_argument("--capture", type=Path, action="append", default=[])
    ingest_ap.set_defaults(action=materialize)
    for command in (prepare_ap, ingest_ap):
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--run", action="store_true", help="write local artifacts; never downloads")
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = args.action(args)
    except (TickDataError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"OPTION-TICK-PREPARATION-FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
