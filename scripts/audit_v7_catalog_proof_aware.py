#!/usr/bin/env python3
"""Deep V7-2 audit with narrowly recorded historical loader hash exceptions."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import pandas as pd

from nn_meta.v7.catalog_audit import audit_catalog
from nn_meta.v7.proposal_store import StoredFeatures
from nn_meta.v7.provenance import runtime_manifest
from nn_meta.v7.storage import identity, sha

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {str(ROOT / "scripts/build_v7_proposals.py"):
           {"f49df275b6c80b364a75f76058fd9c14874cbfe2716d07794958b7722488c4ca"},
           str(ROOT / "nn_meta/v7/catalog_reuse.py"):
           {"73d241359cea764adcada0d01140f66f392daeb9f62e4551bd1e300e028775bf"}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    ids = sorted(pd.read_parquet(args.history / "history.parquet", columns=["security_id"])
                 .security_id.dropna().unique().tolist())
    cache = {}
    exceptions = Counter()
    mismatches = []
    for declaration in args.output.glob("*/*/features/declaration/declaration.json"):
        document = json.loads(declaration.read_text())
        for filename, recorded in {**document["inputs"], **document["sources"]}.items():
            if filename not in cache:
                path = Path(filename)
                cache[filename] = sha(path) if path.is_file() else None
            if recorded == cache[filename]:
                continue
            if recorded in ALLOWED.get(filename, set()):
                exceptions[(Path(filename).name, recorded)] += 1
            else:
                mismatches.append((str(declaration), filename))
    if mismatches:
        raise ValueError(f"unapproved frozen source/input drift: {mismatches[:5]}")
    original = StoredFeatures.verify_bindings
    def verified_historical_bindings(store):
        if identity(runtime_manifest()) != identity(store.declaration["runtime"]):
            raise ValueError("Feature-store runtime changed")
        for filename, recorded in {**store.declaration["inputs"], **store.declaration["sources"]}.items():
            if cache[filename] != recorded and recorded not in ALLOWED.get(filename, set()):
                raise ValueError("Feature-store sources or inputs changed")
    StoredFeatures.verify_bindings = verified_historical_bindings
    try:
        result = audit_catalog(args.output, ids, full=True)
    finally:
        StoredFeatures.verify_bindings = original
    result["historical_hash_exceptions"] = [
        {"path": name, "recorded_sha256": digest, "stores": count}
        for (name, digest), count in sorted(exceptions.items())]
    result["historical_loader_equivalence_proven"] = False
    result["ready_for_7_3"] = False
    result["note"] = "Deep structural receipts passed; historical loader equivalence requires separate proof."
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("audited_stores", "disk_reserve_100gib_passed",
                                                  "historical_hash_exceptions", "ready_for_7_3")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
