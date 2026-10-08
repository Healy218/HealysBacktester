"""V8 events backfill: SEC public-availability rule."""
import importlib.util
from pathlib import Path

import pandas as pd

_SPEC = importlib.util.spec_from_file_location(
    "build_v8_sec", Path(__file__).resolve().parent.parent / "scripts" / "build_v8_sec.py")
sec = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sec)


def _et(s):
    return pd.Timestamp(s, tz="America/New_York").tz_convert("UTC")


def test_availability_rule():
    acc = pd.Series(["2025-05-28T20:21:30.000Z",   # 16:21 ET Wed → as accepted
                     "2025-05-28T22:45:00.000Z",   # 18:45 ET Wed → Thu 06:00 ET
                     "2025-05-30T23:00:00.000Z",   # 19:00 ET Fri → Mon 06:00 ET
                     "2025-05-28T08:00:00.000Z",   # 04:00 ET Wed → Wed 06:00 ET
                     None])                        # no acceptance → filing date + 1 BD 06:00
    filed = pd.Series(["2025-05-28", "2025-05-29", "2025-06-02", "2025-05-28", "2025-05-30"])
    out = sec.available_at(acc, filed)
    assert out[0] == _et("2025-05-28 16:21:30")
    assert out[1] == _et("2025-05-29 06:00")
    assert out[2] == _et("2025-06-02 06:00")
    assert out[3] == _et("2025-05-28 06:00")
    assert out[4] == _et("2025-05-31 06:00")
