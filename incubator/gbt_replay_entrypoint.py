#!/usr/bin/env python3
"""Standalone replay entrypoint for the sealed V6 GBT ensemble."""

from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> int:
    import numpy as np
    import pandas as pd
    import joblib

    request = json.loads(Path(os.environ["AI_INCUBATOR_REQUEST"]).read_text())
    output = Path(os.environ["AI_INCUBATOR_OUTPUT"])
    root = Path(request["snapshot_root"]).resolve()
    relative = Path(request["feature_path"])
    if not root.is_dir() or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("invalid forward feature path")
    source = (root / relative).resolve()
    if root not in source.parents or not source.is_file() or source.is_symlink():
        raise ValueError("forward feature table is unavailable")
    config = json.loads(Path("ensemble_config.json").read_text())
    columns = config.get("features")
    if not isinstance(columns, list) or not columns:
        raise ValueError("ensemble config has no feature contract")
    frame = pd.read_parquet(source)
    missing = sorted(set(columns) - set(frame.columns))
    if missing or frame.empty:
        raise ValueError(f"forward feature table is incomplete: {missing}")
    values = frame[columns].to_numpy(dtype=float)
    if np.isinf(values).any():
        raise ValueError("forward feature table contains infinity")
    predictions, ev_predictions = [], []
    for run_id in config["run_ids"]:
        member = Path(run_id)
        model = joblib.load(member / "model.joblib")
        magnitude = joblib.load(member / "magnitude.joblib")
        predictions.append(model.predict_proba(frame[columns])[:, 1])
        ev_predictions.append(magnitude.predict(frame[columns]))
    score = np.mean(np.vstack(predictions), axis=0)
    ev = np.mean(np.vstack(ev_predictions), axis=0)
    if not np.isfinite(score).all() or not np.isfinite(ev).all():
        raise ValueError("non-finite ensemble prediction")
    mode = config.get("mode", "classification")
    if mode not in {"ev", "classification"}:
        raise ValueError(f"unsupported GBT decision mode: {mode}")
    output.mkdir(parents=True, exist_ok=True)
    outcome = request.get("outcome_column")
    if outcome is not None and outcome not in frame:
        raise ValueError(f"outcome column is unavailable: {outcome}")
    with (output / "results.jsonl").open("w") as handle:
        for index, (win_probability, ev_prediction) in enumerate(zip(score, ev)):
            row = {"prediction": float(ev_prediction if mode == "ev" else win_probability),
                   "p_win": float(win_probability), "ev_prediction": float(ev_prediction)}
            if outcome is not None:
                row["outcome"] = float(frame.iloc[index][outcome])
            handle.write(json.dumps(row) + "\n")
    print(json.dumps({"status": "replayed", "rows": len(frame),
                      "members": len(predictions), "prediction_kind": mode,
                      "outcome_pending": outcome is None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
