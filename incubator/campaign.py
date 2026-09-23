"""Checkpointed verification campaign over discovered artifact bundles."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Iterable

from .checkpoints import Checkpoint
from .budget import ResourceBudget
from .receipts import make_receipt, write_json_atomic
from .sandbox import execute_bundle


def _fingerprint(entries: Iterable[dict[str, Any]], request: dict[str, Any]) -> str:
    payload = repr((sorted(entries, key=lambda item: item["artifact_id"]), request)).encode()
    return hashlib.sha256(payload).hexdigest()


def run_campaign(entries: list[dict[str, Any]], *, request: dict[str, Any], output_dir: Path,
                 run_id: str, checkpoint_path: Path, allow_execution: bool = False,
                 budget: ResourceBudget | None = None) -> dict[str, Any]:
    """Run a resumable, read-only campaign over registry entries."""
    budget = (budget or ResourceBudget()).validate()
    if len(entries) > budget.max_artifacts:
        raise ValueError(f"campaign has {len(entries)} artifacts; budget allows {budget.max_artifacts}")
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    checkpoint = Checkpoint(checkpoint_path, run_id=run_id,
                            input_fingerprint=_fingerprint(entries, request)).load()
    receipts: list[dict[str, Any]] = []
    for entry in entries:
        artifact_id = entry["artifact_id"]
        if checkpoint.is_complete(artifact_id):
            receipts.append(checkpoint.completed[artifact_id]["receipt"])
            continue
        if time.monotonic() - started >= budget.campaign_seconds:
            receipt = make_receipt(run_id=run_id, artifact_id=artifact_id,
                                   artifact_version=entry.get("artifact_version"),
                                   status="failed", error="campaign time budget exceeded",
                                   budget=budget.as_dict())
            write_json_atomic(output_dir / f"{artifact_id}.receipt.json", receipt)
            receipts.append(receipt)
            continue
        try:
            receipt = execute_bundle(Path(entry["bundle"]), request, output_dir,
                                     allow_execution=allow_execution,
                                     timeout_seconds=budget.artifact_seconds,
                                     memory_bytes=budget.memory_bytes,
                                     output_bytes=budget.output_bytes)
            receipt = make_receipt(run_id=run_id, artifact_id=artifact_id,
                                   artifact_version=entry.get("artifact_version"),
                                   status=receipt["status"], sandbox=receipt)
        except Exception as exc:  # one bad candidate must not corrupt the run
            receipt = make_receipt(run_id=run_id, artifact_id=artifact_id,
                                   artifact_version=entry.get("artifact_version"),
                                   status="failed", error=f"{type(exc).__name__}: {exc}")
        receipt.setdefault("budget", budget.as_dict())
        write_json_atomic(output_dir / f"{artifact_id}.receipt.json", receipt)
        receipts.append(receipt)
        if receipt["status"] != "failed":
            checkpoint.mark_complete(artifact_id, receipt)
    summary = {
        "schema": "incubator-campaign-v1",
        "run_id": run_id,
        "artifact_count": len(entries),
        "completed_count": sum(1 for receipt in receipts if receipt["status"] != "failed"),
        "failed_count": sum(1 for receipt in receipts if receipt["status"] == "failed"),
        "receipts": receipts,
        "read_only": True,
        "budget": budget.as_dict(),
        "elapsed_seconds": time.monotonic() - started,
    }
    write_json_atomic(output_dir / "campaign-summary.json", summary)
    return summary
