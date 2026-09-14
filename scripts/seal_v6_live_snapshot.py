"""Validate and seal supplied live inputs without inventing capture/parity evidence.

The draft uses the v6-live-snapshot-v1 schema documented in the runbook. It
references actual bars/raw spot/context/chain and receipt coverage files.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from nn_meta.live.v6_inputs import LiveSnapshot
from nn_meta.v6_expansion import sha256


def seal(draft, output, *, training_inputs, training_sha256, now):
    draft, output = Path(draft).absolute(), Path(output).absolute()
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("sealed snapshot output must be fresh without symlinks")
    original_hash = sha256(draft)
    snapshot = LiveSnapshot(draft, original_hash, now=now)
    snapshot.bind_training(training_inputs, training_sha256)
    # Check every declared symbol before committing a completion receipt.
    for symbol in snapshot.expanded_inputs.document["symbols"]:
        bars = snapshot.bar_loader(symbol)
        snapshot.candidate_kwargs({symbol: bars})
    def absolute_references(value):
        if isinstance(value, dict):
            result = {key: absolute_references(v) for key, v in value.items()}
            if set(result) == {"path", "sha256"} and not Path(result["path"]).is_absolute():
                result["path"] = str(draft.parent / result["path"])
            return result
        if isinstance(value, list):
            return [absolute_references(v) for v in value]
        return value
    document = absolute_references(snapshot.document)
    snapshot.assert_unchanged()
    if sha256(draft) != original_hash:
        raise ValueError("draft changed during sealing")
    output.mkdir(parents=True)
    path = output / "snapshot.json"
    path.write_text(json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n")
    digest = sha256(path)
    checked = LiveSnapshot(path, digest, now=now)
    checked.bind_training(training_inputs, training_sha256)
    checked.assert_unchanged()
    (output / "snapshot.sha256").write_text(digest + "\n")
    (output / "complete.json").write_text(json.dumps({"schema": "v6-live-snapshot-seal-v1",
        "snapshot_sha256": digest, "draft_sha256": original_hash, "research_only": True,
        "scanner_promotion": False, "tick_coverage": "validated per selected request during shadow scan",
        "sources": checked.evidence()["sources"]}, sort_keys=True, indent=2, allow_nan=False) + "\n")
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--training-inputs", type=Path, required=True)
    parser.add_argument("--training-inputs-sha256", required=True)
    a = parser.parse_args()
    print(seal(a.draft, a.output, training_inputs=a.training_inputs,
               training_sha256=a.training_inputs_sha256, now=datetime.now(timezone.utc)))


if __name__ == "__main__":
    main()
