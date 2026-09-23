#!/usr/bin/env python3
"""Join matured V6 forward outcomes to a published incubator feature matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from incubator.outcomes import join_matured_outcomes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-dir", type=Path, required=True)
    parser.add_argument("--outcome-source", action="append", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = join_matured_outcomes(args.feature_dir, args.outcome_source, args.output_dir)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["status"] in {"pending", "replay_ready"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
