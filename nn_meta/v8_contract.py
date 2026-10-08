# nn_meta/v8_contract.py — verify the frozen V8 stage-0 contract.
"""Stage-1 code calls verify() before reading any V8 input: every pinned
artifact must exist with its frozen sha256, or the run refuses to start."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTRACT = REPO / "docs" / "specs" / "V8_CONTRACT_20261008.json"


class ContractError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def describe(path: Path) -> dict:
    return {"path": str(path.relative_to(REPO)), "sha256": sha256(path),
            "bytes": path.stat().st_size}


def verify(contract: Path = CONTRACT, sections=("artifacts",)) -> dict:
    """Check pinned artifacts (and optionally 'code'); return the contract."""
    c = json.loads(contract.read_text())
    bad = []
    for section in sections:
        for name, entry in c[section].items():
            p = REPO / entry["path"]
            if not p.exists():
                bad.append(f"{name}: missing {entry['path']}")
            elif sha256(p) != entry["sha256"]:
                bad.append(f"{name}: sha256 changed {entry['path']}")
    if bad:
        raise ContractError("V8 contract violated:\n  " + "\n  ".join(bad))
    return c
