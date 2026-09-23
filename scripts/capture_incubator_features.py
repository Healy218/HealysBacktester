#!/usr/bin/env python3
"""Capture an immutable model-compatible matrix for incubator replay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from incubator.feature_capture import capture_feature_matrix


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", type=Path, required=True,
                        help="Parquet file or directory; may be repeated")
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--through", required=True)
    parser.add_argument("--outcome-column", default="net_return")
    parser.add_argument("--max-rows", type=int, default=None,
                        help="Optional bounded smoke-capture size")
    args = parser.parse_args()
    try:
        manifest = capture_feature_matrix(args.source, args.output_dir,
                                          args.model_config, args.through,
                                          args.outcome_column, args.max_rows)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(manifest, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
