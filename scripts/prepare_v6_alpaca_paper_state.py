"""Prepare a fresh V6 paper-account state; does not start scanners or orders."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from integrations.alpaca_paper.v6_restart import prepare


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-state", type=Path, required=True)
    parser.add_argument("--new-state", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source_state, args.new_state, args.preflight), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
