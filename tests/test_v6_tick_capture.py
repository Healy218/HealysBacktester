import json

import pytest

from options.data.massive_ticks import TickDataError
from scripts.capture_option_ticks import load_verified_capture
from scripts.run_v6_tick_capture import capture_one
from tests.test_option_tick_dataset import capture, BASE, SECOND, OCC


def test_capture_resume_revalidates_bytes_and_does_not_fetch_again(tmp_path):
    source = capture(tmp_path / "fixture")
    report, rows = load_verified_capture(source)
    calls = []
    class Client:
        def capture(self, contract, kind, start, end, **kwargs):
            calls.append(kind)
            return rows[contract][kind], report["contracts"][0]["captures"][kind]
    batch = {"contracts": [OCC], "start_ns": BASE, "end_ns": BASE+20*SECOND}
    root = tmp_path / "raw"
    root.mkdir()
    result = capture_one(batch, root, client=Client(), reserve_bytes=0)
    assert calls == ["quotes", "trades"]
    assert capture_one(batch, root, client=Client(), reserve_bytes=0) == result
    assert calls == ["quotes", "trades"]
    (result / f"{OCC}.quotes.json.gz").write_bytes(b"changed")
    with pytest.raises(TickDataError, match="SHA256 mismatch"):
        capture_one(batch, root, client=Client(), reserve_bytes=0)


def test_failed_capture_has_no_completion_marker_and_retries_in_fresh_directory(tmp_path):
    class Refused:
        def capture(self, *args, **kwargs):
            raise TickDataError("Massive ticks HTTP 403")
    batch = {"contracts": [OCC], "start_ns": BASE, "end_ns": BASE+20*SECOND}
    root = tmp_path / "raw"
    root.mkdir()
    for _ in range(2):
        with pytest.raises(TickDataError, match="HTTP 403"):
            capture_one(batch, root, client=Refused(), reserve_bytes=0)
    attempts = list(root.glob("*/attempt-*"))
    assert len(attempts) == 2
    assert all((p / "plan.json").exists() and not (p / "manifest.json").exists() for p in attempts)
