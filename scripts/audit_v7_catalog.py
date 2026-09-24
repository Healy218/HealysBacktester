#!/usr/bin/env python3
"""Read-only V7-2 catalog preflight; --full is reserved for post-seal review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nn_meta.v7.catalog_audit import audit_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--max-stores", type=int, default=3)
    parser.add_argument("--full", action="store_true",
                        help="Deep audit every store; use only after the build seals.")
    parser.add_argument("--report", type=Path, help="Optional report outside the active catalog.")
    args = parser.parse_args()
    import pandas as pd
    ids = sorted(pd.read_parquet(args.history / "history.parquet", columns=["security_id"])
                 ["security_id"].dropna().unique().tolist())
    result = audit_catalog(args.output, ids, full=args.full, max_stores=args.max_stores)
    if args.report:
        target = args.report.resolve()
        if target.is_relative_to(args.output.resolve()):
            parser.error("report cannot be written inside the active catalog")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
