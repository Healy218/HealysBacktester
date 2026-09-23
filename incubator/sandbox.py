"""Isolated, opt-in artifact execution boundary."""

from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from .bundles import BundleError, _relative_member, _safe_extract, verify_bundle


def execute_bundle(bundle: Path, request: dict[str, Any], output_dir: Path, *,
                   allow_execution: bool = False, timeout_seconds: int = 120,
                   memory_bytes: int | None = None,
                   output_bytes: int = 16 * 1024**2) -> dict[str, Any]:
    """Verify and optionally execute a manifest-declared entrypoint.

    Execution is disabled by default. Even when explicitly enabled, the
    process runs from a temporary extracted directory, receives a minimal
    environment, uses no shell, and writes only to the caller's output
    directory. OS-level network isolation and resource cgroups remain a later
    deployment gate.
    """
    manifest = verify_bundle(bundle)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    entrypoint = manifest.get("entrypoint")
    receipt: dict[str, Any] = {
        "schema": "incubator-execution-receipt-v1",
        "artifact_id": manifest["artifact_id"],
        "artifact_version": manifest["artifact_version"],
        "bundle": str(bundle.resolve()),
        "request": request,
        "read_only": True,
        "model_loaded": False,
    }
    if not entrypoint:
        receipt.update(status="verified_not_executable", reason="manifest has no entrypoint")
        return receipt
    if not allow_execution:
        receipt.update(status="verified_execution_disabled", reason="explicit execution gate not enabled")
        return receipt
    if timeout_seconds <= 0 or output_bytes <= 0 or (memory_bytes is not None and memory_bytes <= 0):
        raise BundleError("sandbox resource limits must be positive")
    if not isinstance(entrypoint, list) or not entrypoint or not all(isinstance(item, str) and item for item in entrypoint):
        raise BundleError("manifest entrypoint must be a non-empty string list")
    _relative_member(entrypoint[0])
    with tempfile.TemporaryDirectory(prefix="incubator-sandbox-") as temp_name:
        sandbox = Path(temp_name)
        with tarfile.open(bundle, "r:gz") as archive:
            _safe_extract(archive, sandbox)
        command = list(entrypoint)
        entry = _relative_member(command[0])
        if entry.suffix == ".py":
            command = [sys.executable, str(sandbox / entry), *command[1:]]
        else:
            command[0] = str(sandbox / entry)
        request_path = sandbox / "incubator-request.json"
        request_path.write_text(json.dumps(request, sort_keys=True) + "\n")
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONNOUSERSITE": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "TF_NUM_INTRAOP_THREADS": "1",
            "TF_NUM_INTEROP_THREADS": "1",
            "AI_INCUBATOR_READ_ONLY": "1",
            "AI_INCUBATOR_REQUEST": str(request_path),
            "AI_INCUBATOR_OUTPUT": str(output_dir),
        }
        def limit_resources() -> None:
            resource.setrlimit(resource.RLIMIT_CPU, (timeout_seconds, timeout_seconds))
            resource.setrlimit(resource.RLIMIT_FSIZE, (output_bytes, output_bytes))
            if memory_bytes is not None:
                resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))

        completed = subprocess.run(command, cwd=sandbox, env=env, shell=False,
                                   capture_output=True, text=True,
                                   timeout=timeout_seconds, check=False,
                                   preexec_fn=limit_resources)
        receipt.update(
            status="executed" if completed.returncode == 0 else "failed",
            returncode=completed.returncode,
            stdout=completed.stdout[-min(4000, output_bytes):],
            stderr=completed.stderr[-min(4000, output_bytes):],
            python=sys.executable,
        )
        result_file = output_dir / "results.jsonl"
        receipt["model_loaded"] = completed.returncode == 0 and result_file.exists()
        if completed.returncode == 0 and result_file.exists():
            from .metrics import MetricsError, score_jsonl

            try:
                receipt["metrics"] = score_jsonl(result_file)
            except MetricsError as exc:
                records = []
                for line in result_file.read_text().splitlines():
                    if line.strip():
                        records.append(json.loads(line))
                if records and all("prediction" in row and "outcome" not in row for row in records):
                    receipt["status"] = "executed_pending_outcome"
                    receipt["prediction_count"] = len(records)
                else:
                    receipt["status"] = "failed"
                    receipt["metrics_error"] = str(exc)
    return receipt
