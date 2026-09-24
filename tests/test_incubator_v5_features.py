from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from incubator.after_close import load_feature_request
from incubator.v5_features import V5CaptureError, assemble_v5_day, capture_v5_pass


CONFIG = {"family": "nn", "mode": "ev", "features": ["x", "y"]}


def _batch(bar: str, x: float | None = 1.0) -> pd.DataFrame:
    return pd.DataFrame({"symbol": ["SPY"], "strategy": ["ma"], "dte": [5],
                         "entry_ts": [bar], "x": [x], "y": [2.0]})


def test_v5_pass_and_day_are_generation_sealed_and_repeatable(tmp_path: Path) -> None:
    root = tmp_path / "passes"
    first = capture_v5_pass(_batch("2026-09-22T19:15:00Z", None), root, CONFIG,
                            observed_at="2026-09-22T19:16:00Z")
    assert first["generation"] == "v5"
    assert first["missing_value_policy"] == "model_scaler_mean_impute"
    assert capture_v5_pass(_batch("2026-09-22T19:15:00Z", None), root, CONFIG,
                           observed_at="2026-09-22T19:17:00Z")["rows"] == 1
    capture_v5_pass(_batch("2026-09-22T19:30:00Z", 3.0), root, CONFIG,
                    observed_at="2026-09-22T19:31:00Z")
    daily = tmp_path / "daily"
    result = assemble_v5_day(root, daily, CONFIG, through="2026-09-22")
    assert result["rows"] == 2
    assert load_feature_request(daily, generation="v5", as_of="2026-09-22")["feature_path"] == "features.parquet"
    assert assemble_v5_day(root, daily, CONFIG, through="2026-09-22")["rows"] == 2
    with pytest.raises(V5CaptureError, match="changed after sealing"):
        capture_v5_pass(_batch("2026-09-22T19:15:00Z", 7.0), root, CONFIG,
                        observed_at="2026-09-22T19:18:00Z")


def test_v5_capture_rejects_tampered_source_and_wrong_model(tmp_path: Path) -> None:
    root = tmp_path / "passes"
    capture_v5_pass(_batch("2026-09-22T19:15:00Z"), root, CONFIG,
                    observed_at="2026-09-22T19:16:00Z")
    source = root / "2026-09-22" / "20260922T191500Z" / "features.parquet"
    source.write_bytes(b"tampered")
    with pytest.raises(V5CaptureError, match="pass seal/contract mismatch"):
        assemble_v5_day(root, tmp_path / "daily", CONFIG, through="2026-09-22")
    with pytest.raises(V5CaptureError, match="NN/EV"):
        capture_v5_pass(_batch("2026-09-22T19:30:00Z"), root,
                        {"family": "gbt", "mode": "ev", "features": ["x"]},
                        observed_at="2026-09-22T19:31:00Z")
    with pytest.raises(V5CaptureError, match="non-numeric"):
        capture_v5_pass(_batch("2026-09-22T19:45:00Z", "bad"), root, CONFIG,
                        observed_at="2026-09-22T19:46:00Z")
