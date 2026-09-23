"""Shared receipt schema and atomic receipt writes."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


RECEIPT_SCHEMA = "incubator-receipt-v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_receipt(*, run_id: str, artifact_id: str, status: str,
                 artifact_version: str | None = None,
                 metrics: Mapping[str, Any] | None = None,
                 error: str | None = None,
                 **extra: Any) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "receipt_schema": RECEIPT_SCHEMA,
        "run_id": run_id,
        "artifact_id": artifact_id,
        "artifact_version": artifact_version,
        "status": status,
        "recorded_at": utc_now(),
        "read_only": True,
    }
    if metrics is not None:
        receipt["metrics"] = dict(metrics)
    if error is not None:
        receipt["error"] = error
    receipt.update(extra)
    return receipt


def write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    temporary.replace(path)
