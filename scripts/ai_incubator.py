#!/usr/bin/env python3
"""Verify and dry-run immutable AI artifact bundles.

The initial incubator slice is deliberately non-executing. It can package and
verify V5/V6 directories and create receipts, but it cannot touch live alerts,
broker state or source artifacts.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from incubator.bundles import BundleError, create_manifest, pack_directory, verify_bundle
from incubator.budget import BudgetError, ResourceBudget
from incubator.forward import ForwardDataError, load_v6_snapshot
from incubator.campaign import run_campaign
from incubator.metrics import MetricsError, score_jsonl
from incubator.registry import discover, write_registry
from incubator.sandbox import execute_bundle
from incubator.runner import dry_run


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    pack = sub.add_parser("pack", help="create a manifest and immutable tar.gz bundle")
    pack.add_argument("source", type=Path)
    pack.add_argument("output", type=Path)
    pack.add_argument("--artifact-id", required=True)
    pack.add_argument("--artifact-version", required=True)
    pack.add_argument("--artifact-kind", default="option_expert")
    pack.add_argument("--compatibility", default="paper_forward_v1")
    pack.add_argument("--metadata", type=Path)
    pack.add_argument("--keras-replay-entrypoint", action="store_true",
                      help="Embed the standalone Keras replay entrypoint in the bundle")
    pack.add_argument("--gbt-replay-entrypoint", action="store_true",
                      help="Embed the standalone GBT replay entrypoint in the bundle")
    verify = sub.add_parser("verify", help="verify a bundle without executing it")
    verify.add_argument("bundle", type=Path)
    run = sub.add_parser("dry-run", help="verify a bundle and write a no-execution receipt")
    run.add_argument("bundle", type=Path)
    run.add_argument("output_dir", type=Path)
    run.add_argument("--forward-data", type=Path)
    registry = sub.add_parser("discover", help="discover and verify bundles below roots")
    registry.add_argument("roots", nargs="+", type=Path)
    registry.add_argument("--output", type=Path)
    registry.add_argument("--forward-data-contract", default="paper_forward_v1")
    forward = sub.add_parser("inspect-forward", help="verify a sealed V6 forward-data index")
    forward.add_argument("index", type=Path)
    forward.add_argument("--as-of")
    forward.add_argument("--skip-file-hashes", action="store_true")
    sandbox = sub.add_parser("sandbox-run", help="verify or explicitly run a manifest entrypoint")
    sandbox.add_argument("bundle", type=Path)
    sandbox.add_argument("request", type=Path)
    sandbox.add_argument("output_dir", type=Path)
    sandbox.add_argument("--allow-execution", action="store_true")
    sandbox.add_argument("--timeout-seconds", type=int, default=120)
    sandbox.add_argument("--memory-bytes", type=int, default=2 * 1024**3)
    sandbox.add_argument("--output-bytes", type=int, default=16 * 1024**2)
    metrics = sub.add_parser("metrics", help="score JSONL prediction/outcome records")
    metrics.add_argument("results", type=Path)
    metrics.add_argument("--output", type=Path)
    campaign = sub.add_parser("campaign", help="run a checkpointed verify/dry-run campaign")
    campaign.add_argument("roots", nargs="+", type=Path)
    campaign.add_argument("--request", type=Path, required=True)
    campaign.add_argument("--output-dir", type=Path, required=True)
    campaign.add_argument("--checkpoint", type=Path, required=True)
    campaign.add_argument("--run-id", required=True)
    campaign.add_argument("--allow-execution", action="store_true")
    campaign.add_argument("--campaign-seconds", type=float, default=3600.0)
    campaign.add_argument("--artifact-seconds", type=int, default=120)
    campaign.add_argument("--memory-bytes", type=int, default=2 * 1024**3)
    campaign.add_argument("--output-bytes", type=int, default=16 * 1024**2)
    campaign.add_argument("--max-artifacts", type=int, default=64)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "pack":
            metadata = json.loads(args.metadata.read_text()) if args.metadata else None
            source = args.source
            with tempfile.TemporaryDirectory(prefix="incubator-source-") as temp_name:
                if args.keras_replay_entrypoint and args.gbt_replay_entrypoint:
                    raise BundleError("choose one replay entrypoint")
                if args.keras_replay_entrypoint or args.gbt_replay_entrypoint:
                    source = Path(temp_name) / "artifact"
                    shutil.copytree(args.source, source, symlinks=False)
                    entrypoint = ("keras_replay_entrypoint.py" if args.keras_replay_entrypoint
                                  else "gbt_replay_entrypoint.py")
                    shutil.copy2(REPO_ROOT / f"incubator/{entrypoint}",
                                 source / "replay_entrypoint.py")
                    (source / "replay_entrypoint.py").chmod(0o755)
                manifest = create_manifest(
                    source,
                    artifact_id=args.artifact_id,
                    artifact_version=args.artifact_version,
                    artifact_kind=args.artifact_kind,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    compatibility={"forward_data_contract": args.compatibility},
                    metadata=metadata,
                )
                if args.keras_replay_entrypoint or args.gbt_replay_entrypoint:
                    manifest["entrypoint"] = ["replay_entrypoint.py"]
                    manifest["manifest_sha256"] = __import__("incubator.bundles", fromlist=["manifest_digest"]).manifest_digest(manifest)
                pack_directory(source, args.output, manifest=manifest)
            print(json.dumps({"status": "packed", "bundle": str(args.output.resolve()), "manifest": manifest}, sort_keys=True, indent=2))
        elif args.command == "verify":
            print(json.dumps({"status": "verified", "manifest": verify_bundle(args.bundle)}, sort_keys=True, indent=2))
        elif args.command == "dry-run":
            print(json.dumps(dry_run(args.bundle, output_dir=args.output_dir, forward_data=args.forward_data), sort_keys=True, indent=2))
        elif args.command == "inspect-forward":
            snapshot = load_v6_snapshot(args.index, as_of=args.as_of, verify_files=not args.skip_file_hashes)
            print(json.dumps({"status": "verified", "root": str(snapshot.root), "through": snapshot.through,
                              "manifest_sha256": snapshot.manifest_sha256, "files": len(snapshot.manifest["files"])}, sort_keys=True, indent=2))
        elif args.command == "sandbox-run":
            request = json.loads(args.request.read_text())
            print(json.dumps(execute_bundle(args.bundle, request, args.output_dir,
                                            allow_execution=args.allow_execution,
                                            timeout_seconds=args.timeout_seconds,
                                            memory_bytes=args.memory_bytes,
                                            output_bytes=args.output_bytes), sort_keys=True, indent=2))
        elif args.command == "metrics":
            result = score_jsonl(args.results)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
            print(json.dumps(result, sort_keys=True, indent=2))
        elif args.command == "campaign":
            entries = discover(args.roots)
            request = json.loads(args.request.read_text())
            budget = ResourceBudget(campaign_seconds=args.campaign_seconds,
                                    artifact_seconds=args.artifact_seconds,
                                    memory_bytes=args.memory_bytes,
                                    output_bytes=args.output_bytes,
                                    max_artifacts=args.max_artifacts)
            print(json.dumps(run_campaign(entries, request=request, output_dir=args.output_dir,
                                           run_id=args.run_id, checkpoint_path=args.checkpoint,
                                           allow_execution=args.allow_execution,
                                           budget=budget), sort_keys=True, indent=2))
        else:
            entries = discover(args.roots, forward_data_contract=args.forward_data_contract)
            if args.output:
                write_registry(entries, args.output)
            print(json.dumps({"status": "discovered", "count": len(entries), "artifacts": entries}, sort_keys=True, indent=2))
        return 0
    except (BundleError, BudgetError, ForwardDataError, MetricsError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"incubator refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
