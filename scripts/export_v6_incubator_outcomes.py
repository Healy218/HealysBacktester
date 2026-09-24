#!/usr/bin/env python3
"""Export closed V6 paper outcomes, optionally joining one sealed candidate day."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from incubator.outcomes import join_matured_outcomes
from incubator.v6_paper_outcomes import export_v6_paper_outcomes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--through", required=True, help="UTC close date, YYYY-MM-DD")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--feature-dir", type=Path)
    parser.add_argument("--join-dir", type=Path)
    args = parser.parse_args()
    if bool(args.feature_dir) != bool(args.join_dir):
        parser.error("--feature-dir and --join-dir must be supplied together")
    result = export_v6_paper_outcomes(args.database, args.output_dir, through=args.through)
    if args.feature_dir:
        result["join"] = join_matured_outcomes(
            args.feature_dir, [args.output_dir / "outcomes.parquet"], args.join_dir)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
