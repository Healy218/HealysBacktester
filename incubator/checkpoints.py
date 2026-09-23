"""Atomic, fail-closed campaign checkpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .receipts import utc_now, write_json_atomic


class CheckpointError(ValueError):
    """Raised when a checkpoint is incompatible with a campaign."""


class Checkpoint:
    def __init__(self, path: Path, *, run_id: str, input_fingerprint: str):
        self.path = path
        self.run_id = run_id
        self.input_fingerprint = input_fingerprint
        self.completed: dict[str, dict[str, Any]] = {}

    def load(self) -> "Checkpoint":
        if not self.path.exists():
            return self
        try:
            value = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise CheckpointError(f"invalid checkpoint: {self.path}") from exc
        if value.get("schema") != "incubator-checkpoint-v1":
            raise CheckpointError("unsupported checkpoint schema")
        if value.get("run_id") != self.run_id:
            raise CheckpointError("checkpoint run_id mismatch")
        if value.get("input_fingerprint") != self.input_fingerprint:
            raise CheckpointError("checkpoint input fingerprint mismatch")
        completed = value.get("completed", {})
        if not isinstance(completed, dict):
            raise CheckpointError("checkpoint completed field must be an object")
        self.completed = completed
        return self

    def save(self) -> None:
        write_json_atomic(self.path, {
            "schema": "incubator-checkpoint-v1",
            "run_id": self.run_id,
            "input_fingerprint": self.input_fingerprint,
            "updated_at": utc_now(),
            "completed": self.completed,
        })

    def mark_complete(self, artifact_id: str, receipt: dict[str, Any]) -> None:
        self.completed[artifact_id] = {"status": receipt.get("status"), "receipt": receipt}
        self.save()

    def is_complete(self, artifact_id: str) -> bool:
        return artifact_id in self.completed
