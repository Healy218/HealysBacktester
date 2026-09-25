#!/usr/bin/env python3
"""Recreate each old-loader security input and compare its frozen feature declaration."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from nn_meta.v7.causal_features import CausalFeatures
from nn_meta.v7.proposal_store import _frame_identity
from nn_meta.v7.storage import sha
from scripts.build_v7_proposals import load_inputs
import nn_meta.v7.storage as storage

ROOT = Path(__file__).resolve().parents[1]
OLD = "f49df275b6c80b364a75f76058fd9c14874cbfe2716d07794958b7722488c4ca"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("output", "source", "history", "actions", "action-coverage",
                 "supplemental-coverage", "previous-supplemental-coverage",
                 "reuse-manifest", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    original_sha = storage.sha
    digest_cache = {}
    def checked_sha(path):
        target = Path(path)
        stat = target.stat()
        key = (str(target.resolve()), stat.st_size, stat.st_mtime_ns)
        if key not in digest_cache:
            digest_cache[key] = original_sha(target)
        return digest_cache[key]
    storage.sha = checked_sha
    bound = {sha(path / "complete.json"): path for path in
             (args.action_coverage, args.supplemental_coverage,
              args.previous_supplemental_coverage)}
    exceptions = []
    reused = set(json.loads(args.reuse_manifest.read_text())["securities"])
    for path in sorted(args.output.glob("*/5/features/declaration/declaration.json")):
        declaration = json.loads(path.read_text())
        if (declaration["inputs"].get(str(ROOT / "scripts/build_v7_proposals.py")) == OLD
                and declaration["security_id"] not in reused):
            exceptions.append((declaration["security_id"], path))
    passed = []
    for security_id, path in exceptions:
        declaration = json.loads(path.read_text())
        coverage_sha = declaration["action_coverage"]["receipt_sha256"]
        coverage = bound.get(coverage_sha)
        if coverage is None:
            raise ValueError(f"unknown bound coverage: {security_id}")
        payload = dict(source=args.source.resolve(), history=args.history.resolve(),
                       actions=args.actions.resolve(), action_coverage=coverage.resolve(), security_id=security_id,
                       raw_supplement=[], start="2022-03-15", end="2026-09-14")
        raw, actions, calendar, inputs, routing, eligibility, coverage_doc = load_inputs(payload)
        if set(inputs) != set(declaration["inputs"]):
            raise ValueError(f"input path set changed: {security_id}")
        for filename, digest in declaration["inputs"].items():
            if filename != str(ROOT / "scripts/build_v7_proposals.py") and inputs[filename] != digest:
                raise ValueError(f"input changed: {security_id}: {filename}")
        for minutes in (5, 15, 30):
            current = json.loads((args.output / security_id / str(minutes) / "features/declaration/declaration.json").read_text())
            proposal = json.loads((args.output / security_id / str(minutes) / "proposals/declaration/declaration.json").read_text())
            chart = CausalFeatures(raw, actions, calendar, security_id=security_id, minutes=minutes,
                                   start="2022-03-15", end="2026-09-14")
            action_rows = []
            for action in chart.history.actions:
                row = asdict(action)
                for key in ("effective_at", "available_at"):
                    row[key] = row[key].isoformat()
                action_rows.append(row)
            if (_frame_identity(chart.history.raw) != current["raw_identity"] or
                    coverage_doc != current["action_coverage"] or
                    action_rows != current["actions"] or calendar != current["calendar"] or
                    routing != proposal["symbols_by_date"] or
                    eligibility.binding != proposal["entry_eligibility"]):
                raise ValueError(f"current loader output differs: {security_id}/{minutes}")
        passed.append(security_id)
        if len(passed) % 10 == 0:
            print(json.dumps({"proved": len(passed), "target": len(exceptions)}), flush=True)
    report = {"schema": "v7-historical-loader-equivalence-v1", "target": len(exceptions),
              "proved": len(passed), "security_ids": passed,
              "old_loader_sha256": OLD, "current_loader_sha256": sha(ROOT / "scripts/build_v7_proposals.py")}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"proved": len(passed), "target": len(exceptions)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
