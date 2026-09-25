"""Prepare a separate, empty V6 state bound to a verified Alpaca paper account."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def prepare(source_state: Path, new_state: Path, preflight_path: Path, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("preparation time must be timezone aware")
    source_state, new_state, preflight_path = map(Path, (source_state, new_state, preflight_path))
    if not source_state.is_dir() or source_state.is_symlink() or new_state.exists() or new_state.is_symlink():
        raise ValueError("source state must exist and destination must be new")
    if new_state.resolve().is_relative_to(source_state.resolve()):
        raise ValueError("new state cannot be inside the old state")
    review = json.loads(preflight_path.read_text())
    account = review.get("alpaca", {})
    if (review.get("schema") != "v6-alpaca-paper-preflight-v1" or
            review.get("order_submission_enabled") is not False or
            account.get("source") != "alpaca-paper-read-only" or
            account.get("long_option_entry_eligible") is not True or
            account.get("position_count") != 0 or account.get("open_order_count") != 0 or
            account.get("open_orders_may_be_truncated") is not False or
            not isinstance(account.get("account_fingerprint"), str) or
            len(account["account_fingerprint"]) != 64):
        raise ValueError("fresh, empty, eligible Alpaca paper account preflight required")
    observed = datetime.fromisoformat(account["observed_at"])
    if observed.tzinfo is None or not 0 <= (now - observed).total_seconds() <= 3600:
        raise ValueError("paper account preflight is stale")
    activation_path, index_path = source_state / "activation.json", source_state / "data-index.json"
    activation, index = json.loads(activation_path.read_text()), json.loads(index_path.read_text())
    if (activation.get("status") != "passed" or activation.get("broker_orders") is not False or
            index.get("schema") != "v6-forward-data-index-v1" or
            index.get("release_sha256") != activation.get("release_sha256")):
        raise ValueError("V6 release/activation mismatch")
    checkout = source_state.parents[2]
    for relative, expected in activation.get("runtime_sha256", {}).items():
        path = checkout / relative
        if not path.is_file() or digest(path) != expected:
            raise ValueError(f"V6 runtime hash mismatch: {relative}")
    data_path = Path(index["path"]) / "manifest.json"
    if not data_path.is_file() or digest(data_path) != index["sha256"]:
        raise ValueError("V6 data pointer failed hash check")
    manifest = {
        "schema": "v6-alpaca-paper-restart-prepared-v1",
        "prepared_at": now.isoformat(),
        "account_fingerprint": account["account_fingerprint"],
        "old_state": str(source_state.resolve()),
        "historical_positions_imported": False,
        "sizing_base": "current_alpaca_options_buying_power",
        "release_sha256": activation["release_sha256"],
        "data_sha256": index["sha256"],
        "data_index_source": str(index_path.resolve()),
        "preflight_sha256": digest(preflight_path),
        "order_submission_enabled": False,
        "scanner_enabled": False,
    }
    new_state.mkdir(mode=0o700, parents=False)
    for name, raw in (("activation.json", activation_path.read_bytes()),
                      ("data-index.json", index_path.read_bytes()),
                      ("paper-restart.json", (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())):
        target = new_state / name
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
            stream.write(raw)
    return manifest
