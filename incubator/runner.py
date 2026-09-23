"""Read-only incubator dry-run and receipt generation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .bundles import BundleError, verify_bundle
from .receipts import make_receipt, write_json_atomic


def dry_run(bundle: Path, *, output_dir: Path, forward_data: Path | None = None) -> dict[str, Any]:
    """Verify a bundle and emit a non-executing receipt.

    This is intentionally the only supported execution mode in the first
    slice. It proves discovery/verification/receipt behavior without loading a
    model or connecting to live state.
    """
    manifest = verify_bundle(bundle)
    if forward_data is not None and not forward_data.is_file():
        raise BundleError(f"forward data does not exist: {forward_data}")
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt = make_receipt(
        run_id="single-dry-run",
        artifact_id=manifest["artifact_id"],
        artifact_version=manifest["artifact_version"],
        status="verified_not_executed",
        bundle=str(bundle.resolve()),
        bundle_sha256=hashlib.sha256(bundle.read_bytes()).hexdigest(),
        forward_data=str(forward_data.resolve()) if forward_data else None,
        execution={"mode": "dry-run", "read_only": True, "model_loaded": False},
    )
    receipt_path = output_dir / f"{manifest['artifact_id']}.json"
    write_json_atomic(receipt_path, receipt)
    return receipt
