from __future__ import annotations

import json
from pathlib import Path
import shutil

import pandas as pd
import pytest

from incubator.v5_features import V5CaptureError, capture_v5_pass
from scripts.stage_v5_incubator_passes import stage_day


CONFIG = {"family": "nn", "mode": "ev", "features": ["x"]}


def test_stage_v5_day_validates_before_publishing_and_is_repeatable(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "server"
    frame = pd.DataFrame({"symbol": ["SPY"], "strategy": ["ma"], "dte": [5],
                          "entry_ts": ["2026-09-24T13:30:00Z"], "x": [1.0]})
    capture_v5_pass(frame, source, CONFIG, observed_at="2026-09-24T13:31:00Z")
    config = tmp_path / "config.json"
    config.write_text(json.dumps(CONFIG))
    destination = tmp_path / "home"

    def copy_day(command, *, check, timeout):
        assert command[:5] == ["rsync", "-a", "-e", "ssh -o BatchMode=yes", "--"]
        assert check is True and timeout == 180
        shutil.copytree(source / "2026-09-24", Path(command[-1]), dirs_exist_ok=True)

    monkeypatch.setattr("scripts.stage_v5_incubator_passes.subprocess.run", copy_day)
    result = stage_day(as_of="2026-09-24", destination=destination, model_config=config,
                       remote="user@example.com", remote_root="/remote/passes")
    assert result == {"through": "2026-09-24", "passes": 1, "rows": 1,
                      "status": "staged_and_verified"}
    assert stage_day(as_of="2026-09-24", destination=destination, model_config=config,
                     remote="user@example.com", remote_root="/remote/passes")["status"] == "already_staged_and_verified"
    staged = next((destination / "2026-09-24").glob("*/features.parquet"))
    staged.write_bytes(b"corrupt")
    with pytest.raises(V5CaptureError, match="seal/contract mismatch"):
        stage_day(as_of="2026-09-24", destination=destination, model_config=config,
                  remote="user@example.com", remote_root="/remote/passes")


def test_stage_v5_rejects_remote_shell_text(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="remote"):
        stage_day(as_of="2026-09-24", destination=tmp_path, model_config=tmp_path / "no.json",
                  remote="host;bad", remote_root="/remote/passes")


def test_stage_v5_requires_every_calendar_bar(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "server"
    capture_v5_pass(pd.DataFrame({"symbol": ["SPY"], "strategy": ["ma"], "dte": [5],
                     "entry_ts": ["2026-09-24T13:30:00Z"], "x": [1.0]}), source, CONFIG,
                    observed_at="2026-09-24T13:31:00Z")
    config = tmp_path / "config.json"
    config.write_text(json.dumps(CONFIG))
    (tmp_path / "calendar.json").write_text(json.dumps({"sessions": [
        {"date": "2026-09-24", "open": "09:30", "close": "10:00"}]}))
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"path": str(tmp_path)}))

    def copy_day(command, *, check, timeout):
        shutil.copytree(source / "2026-09-24", Path(command[-1]), dirs_exist_ok=True)

    monkeypatch.setattr("scripts.stage_v5_incubator_passes.subprocess.run", copy_day)
    target = tmp_path / "home" / "2026-09-24"
    with pytest.raises(ValueError, match="session incomplete: 1/2"):
        stage_day(as_of="2026-09-24", destination=target.parent, model_config=config,
                  remote="user@example.com", remote_root="/remote/passes", calendar_index=index)
    assert not target.exists()
