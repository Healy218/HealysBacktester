#!/usr/bin/env python3
"""Run the read-only incubator campaign after market close.

This entrypoint is safe to schedule, but production activation remains an
explicit deployment decision: execution is disabled unless the caller opts in.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from incubator.budget import ResourceBudget
from incubator.campaign import run_campaign
from incubator.forward import load_v6_snapshot
from incubator.registry import discover


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--v6-index", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--campaign-seconds", type=float, default=3600.0)
    parser.add_argument("--artifact-seconds", type=int, default=120)
    parser.add_argument("--memory-bytes", type=int, default=2 * 1024**3)
    parser.add_argument("--output-bytes", type=int, default=16 * 1024**2)
    parser.add_argument("--max-artifacts", type=int, default=64)
    parser.add_argument("--allow-execution", action="store_true",
                        help="Explicitly opt into sandbox entrypoints; default is verification-only.")
    args = parser.parse_args()
    snapshot = load_v6_snapshot(args.v6_index, as_of=args.as_of)
    entries = discover([args.bundle_root])
    cutoff = args.as_of or snapshot.through
    request = snapshot.request(artifact_id="after-close-campaign", as_of=cutoff)
    request["campaign_mode"] = "after-close-read-only"
    run_id = args.run_id or f"close-{date.fromisoformat(cutoff):%Y%m%d}"
    budget = ResourceBudget(campaign_seconds=args.campaign_seconds,
                            artifact_seconds=args.artifact_seconds,
                            memory_bytes=args.memory_bytes,
                            output_bytes=args.output_bytes,
                            max_artifacts=args.max_artifacts)
    summary = run_campaign(entries, request=request, output_dir=args.output_dir,
                           run_id=run_id, checkpoint_path=args.checkpoint,
                           allow_execution=args.allow_execution, budget=budget)
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0 if summary["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
