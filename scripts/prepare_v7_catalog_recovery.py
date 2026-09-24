#!/usr/bin/env python3
"""Certify reusable V7 stores and archive only incompatible/partial securities."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nn_meta.v7.catalog_audit import expected_variants
from nn_meta.v7.catalog_reuse import (actions_by_security, check_admitted_actions,
                                      compatible_security, current_source_hashes)
from nn_meta.v7.storage import sha


def main() -> None:
    import pandas as pd
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("output", "history", "old-actions", "actions", "coverage", "manifest"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--apply", action="store_true",
                        help="Archive nonreusable securities and seal the reuse manifest")
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / "nn_meta"):
        parser.error("Catalog must remain under nn_meta")
    if args.manifest.exists():
        parser.error("Recovery manifest already exists")
    gate = check_admitted_actions(args.history, args.actions, args.coverage)
    ids = sorted(pd.read_parquet(args.history / "history.parquet", columns=["security_id"])
                 .security_id.unique().tolist())
    grouped = actions_by_security(args.actions)
    old_sha = sha(args.old_actions / "actions.json")
    variants = expected_variants()
    current_sources = current_source_hashes()
    reusable = {}
    for security_id in ids:
        receipts = compatible_security(args.output, security_id, grouped.get(security_id, []),
            old_action_sha=old_sha, coverage_sha=gate["coverage_sha256"], variants=variants,
            current_sources=current_sources)
        if receipts is not None:
            reusable[security_id] = receipts
    archive = args.output.with_name(args.output.name + "-superseded-20260924")
    to_archive = [security_id for security_id in ids if security_id not in reusable
                  and (args.output / security_id).exists()]
    summary = {"expected_securities": len(ids), "reusable_complete": len(reusable),
               "archive_existing": len(to_archive), "remaining_builds": len(ids) - len(reusable),
               "archive": str(archive), **gate}
    print(json.dumps(summary, sort_keys=True), flush=True)
    if not args.apply:
        return
    lock_path = args.output / ".catalog-run.lock"
    with lock_path.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        archive.mkdir(exist_ok=True)
        for security_id in to_archive:
            old = args.output / security_id
            destination = archive / security_id
            if destination.exists():
                raise FileExistsError(destination)
            os.rename(old, destination)
        document = {"schema": "v7-catalog-reuse-v1", "output": str(args.output.resolve()),
                    "old_actions": str(args.old_actions.resolve()),
                    "old_actions_sha256": old_sha,
                    "new_actions_sha256": gate["actions_sha256"],
                    "coverage_sha256": gate["coverage_sha256"],
                    "admitted_events": gate["admitted_events"],
                    "securities": reusable,
                    "archived_security_ids": to_archive,
                    "archive": str(archive.resolve())}
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        temp = args.manifest.with_name(args.manifest.name + ".partial-" + uuid.uuid4().hex)
        with temp.open("x") as stream:
            stream.write(json.dumps(document, sort_keys=True, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.rename(temp, args.manifest)
    print(json.dumps({"manifest": str(args.manifest), "reuse": len(reusable),
                      "archived": len(to_archive)}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
