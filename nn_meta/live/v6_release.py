"""Portable, hash-verified frozen GBT inference without the training runtime."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024**2), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def member_path(root, name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("release path escapes its directory")
    target = Path(root) / path
    if any(p.is_symlink() for p in (target, *target.parents)):
        raise ValueError("release references cannot contain symlinks")
    return target


def verify_release(root, anchor):
    root = Path(root)
    if sha(member_path(root, "release.json")) != anchor:
        raise ValueError("release differs from its external hash anchor")
    release = read(root / "release.json")
    if release.get("schema") != "v6-server-release-v1":
        raise ValueError("unsupported V6 server release")
    for name, digest in release["files"].items():
        if sha(member_path(root, name)) != digest:
            raise ValueError(f"release file changed: {name}")
    cfg = read(root / "model/ensemble_config.json")
    manifest = read(root / "model/manifest.json")
    if (cfg.get("family") != "gbt" or cfg.get("mode") != "ev"
            or cfg.get("threshold") != .05 or cfg.get("dd_brake") is not None
            or len(cfg.get("run_ids", [])) != 40 or len(set(cfg["run_ids"])) != 40
            or len(cfg.get("features", [])) != 164 or cfg.get("label") != "label_excess"):
        raise ValueError("release is not the frozen V6 40-member EV policy")
    required = {"ensemble_config.json"}
    for run in cfg["run_ids"]:
        if Path(run).name != run or run in (".", ".."):
            raise ValueError("invalid model member path")
        required.update(f"{run}/{head}.joblib" for head in ("model", "magnitude"))
    if not required <= set(manifest["output_artifacts"]):
        raise ValueError("bundle manifest omits a scoring artifact")
    for name, digest in manifest["output_artifacts"].items():
        if release["files"].get("model/" + name) != digest:
            raise ValueError("release/model artifact binding differs")
    if release["files"].get("baseline_spec.json") != manifest["baseline_spec"]["sha256"]:
        raise ValueError("release baseline differs from trained baseline")
    if release["files"].get("model/ensemble_config.json") != release["model_sha256"]:
        raise ValueError("release model identity differs")
    return release


class FrozenGBT:
    """Both trained heads, in the exact persisted member/feature order."""
    def __init__(self, root, anchor):
        import joblib
        self.root = Path(root)
        self.release = verify_release(root, anchor)
        self.config = read(self.root / "model/ensemble_config.json")
        self.family, self.mode = "gbt", "ev"
        self.threshold, self.dd_brake = self.config["threshold"], None
        self.features = self.config["features"]
        self.eligible = self.config["eligible"]
        self.members = [{head: joblib.load(self.root / "model" / run / f"{head}.joblib")
                         for head in ("model", "magnitude")} for run in self.config["run_ids"]]

    def _predict(self, rows, head):
        missing = set(self.features) - set(rows)
        if missing:
            raise ValueError(f"V6 missing {len(missing)} features: {sorted(missing)}")
        values = rows[self.features]
        if np.isinf(values.to_numpy(dtype=float)).any():
            raise ValueError("V6 features contain infinity")
        predictions = []
        for member in self.members:
            model = member[head]
            result = (model.predict_proba(values, num_threads=1)[:, 1]
                      if head == "model" else model.predict(values, num_threads=1))
            if np.asarray(result).shape != (len(rows),) or not np.isfinite(result).all():
                raise ValueError("V6 member produced invalid predictions")
            predictions.append(result)
        return np.mean(predictions, axis=0)

    def score(self, rows):
        return self._predict(rows, "model")

    def ev(self, rows):
        return self._predict(rows, "magnitude")

    def selftest(self):
        rows = pd.read_parquet(self.root / "prediction_probe.parquet")
        actual = {"pred_ensemble": self.score(rows), "ev_ensemble": self.ev(rows)}
        errors = {}
        for name, values in actual.items():
            expected = rows[name].to_numpy()
            if not np.isfinite(expected).all():
                raise ValueError("nonfinite reference predictions")
            errors[name] = float(np.max(np.abs(values - expected)))
            if not np.allclose(values, expected, rtol=1e-9, atol=1e-10):
                raise ValueError(f"frozen prediction replay differs: {name}: {errors[name]}")
        return {"status": "passed", "rows": len(rows), "members": len(self.members),
                "features": len(self.features), "max_absolute_error": errors,
                "model_sha256": self.release["model_sha256"],
                "validation": "saved historical predictions, not live input or execution validation"}
