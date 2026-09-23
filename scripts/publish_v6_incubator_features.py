#!/usr/bin/env python3
"""Publish current V6 candidate features for later incubator outcome joining."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from incubator.live_features import publish_v6_features


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--through", required=True)
    args = parser.parse_args()
    try:
        manifest = publish_v6_features(args.source, args.output_dir, args.model_config, args.through)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(manifest, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
