"""Package a completed V6 model with portable context and prediction evidence."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from nn_meta.live.v6_release import sha, read, FrozenGBT

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def package(campaign, inputs, output):
    from scripts.v6_training_pipeline import training_outputs
    base = ROOT / "nn_meta/campaigns" / campaign / "v6"
    training_outputs(base)
    output = Path(output).absolute()
    if output.exists():
        raise ValueError("preserve earlier releases; output must be fresh")
    output.mkdir(parents=True)
    manifest = read(base / "model_final/manifest.json")
    cfg = read(base / "model_final/ensemble_config.json")
    for name, digest in manifest["output_artifacts"].items():
        source = base / "model_final" / name
        if sha(source) != digest:
            raise ValueError(f"frozen model changed: {name}")
        dest = output / "model" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    shutil.copyfile(base / "model_final/manifest.json", output / "model/manifest.json")
    shutil.copyfile(base / "artifacts/baseline_spec.json", output / "baseline_spec.json")
    if sha(output / "baseline_spec.json") != manifest["baseline_spec"]["sha256"]:
        raise ValueError("trained baseline changed")
    original = read(inputs)
    portable = deepcopy(original)
    refs = {}

    def reference(ref):
        source = Path(ref["path"])
        if not source.is_absolute():
            source = inputs.parent / source
        if sha(source) != ref["sha256"]:
            raise ValueError("frozen input reference changed")
        name = "references/" + ref["sha256"] + source.suffix
        dest = output / name
        dest.parent.mkdir(exist_ok=True)
        if not dest.exists():
            shutil.copyfile(source, dest)
        refs[str(source)] = {"path": name, "sha256": ref["sha256"]}
        return refs[str(source)]

    portable["context_references"] = [reference(r) for r in original.get("context_references", [])]
    for symbol, entry in portable["symbols"].items():
        for key in ("timeframe_flags", "vwap_observations"):
            if entry.get(key):
                entry[key] = reference(entry[key])
    # Preserve policy object byte-for-byte semantically; its evidence paths are
    # historic lineage. Live input materialization must explicitly rebind them.
    write(output / "training-inputs.json", portable)
    shutil.copyfile(inputs, output / "original-training-inputs.json")
    write(output / "relocated-references.json", refs)
    predictions = pd.read_parquet(base / "reports/finalize_val_predictions.parquet")
    indices = sorted(set(np.linspace(0, len(predictions)-1, 128, dtype=int).tolist()
                         + [int(predictions.ev_ensemble.idxmax()), int(predictions.ev_ensemble.idxmin())]))
    keys = ["symbol", "strategy", "trade_idx", "dte", "entry_ts"]
    probe = predictions.iloc[indices][[*keys, "trade_id", "pred_ensemble", "ev_ensemble"]]
    rows = pd.read_parquet(base / "artifacts/meta_dataset.parquet",
        columns=[*keys, *cfg["features"]],
        filters=[("entry_ts", "in", probe.entry_ts.tolist()), ("symbol", "in", probe.symbol.tolist())])
    probe = probe.merge(rows, on=keys, how="left", validate="one_to_one", indicator=True)
    if not probe._merge.eq("both").all():
        raise ValueError("prediction probe identities differ")
    probe = probe.drop(columns="_merge")
    probe.to_parquet(output / "prediction_probe.parquet", index=False)
    release = {"schema": "v6-server-release-v1", "campaign": campaign,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_sha256": sha(output / "model/ensemble_config.json"),
        "original_training_inputs_sha256": sha(inputs),
        "training_scope_sha256": sha(base / "continuation_scope.json"),
        "training_inputs_sha256": sha(output / "training-inputs.json"),
        "initial_mode": "record_only", "alerts_enabled": False,
        "portfolio": {"max_concurrent": 5, "position_fraction": .1, "one_position_per_symbol": True},
        "files": {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()}}
    write(output / "release.json", release)
    anchor = sha(output / "release.json")
    (output / "release.sha256").write_text(anchor + "\n")
    result = FrozenGBT(output, anchor).selftest()
    print(json.dumps({"release": str(output), "anchor": anchor, "selftest": result}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--inputs", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    package(args.campaign, args.inputs, args.output)
