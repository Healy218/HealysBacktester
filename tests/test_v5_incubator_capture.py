import pandas as pd
import pytest

from incubator.v5_features import V5CaptureError, assemble_v5_day, capture_v5_pass


CONFIG = {"family": "nn", "mode": "ev", "features": ["x", "y"]}


def _batch(bar, x=1.0):
    return pd.DataFrame({"symbol": ["SPY"], "strategy": ["ma"], "dte": [5],
                         "entry_ts": [bar], "x": [x], "y": [2.0]})


def test_v5_capture_seals_and_assembles_genuine_generation(tmp_path):
    root = tmp_path / "passes"
    first = capture_v5_pass(_batch("2026-09-23T19:15:00Z", None), root, CONFIG,
                            observed_at="2026-09-23T19:16:00Z")
    assert first["generation"] == "v5"
    assert capture_v5_pass(_batch("2026-09-23T19:15:00Z", None), root, CONFIG,
                           observed_at="2026-09-23T19:17:00Z")["rows"] == 1
    capture_v5_pass(_batch("2026-09-23T19:30:00Z", 3.0), root, CONFIG,
                    observed_at="2026-09-23T19:31:00Z")
    day = assemble_v5_day(root, tmp_path / "daily", CONFIG, through="2026-09-23")
    assert day["rows"] == 2 and day["outcome_status"] == "pending"
    with pytest.raises(V5CaptureError, match="changed after sealing"):
        capture_v5_pass(_batch("2026-09-23T19:15:00Z", 7.0), root, CONFIG,
                        observed_at="2026-09-23T19:18:00Z")
    with pytest.raises(V5CaptureError, match="non-numeric"):
        capture_v5_pass(_batch("2026-09-23T19:45:00Z", "bad"), root, CONFIG,
                        observed_at="2026-09-23T19:46:00Z")
