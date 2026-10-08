"""V8.0-liquidity admission: decision-time inputs and first-failure reasons."""
import importlib.util
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("build_v8_admission",
                                               ROOT / "scripts" / "build_v8_admission.py")
adm = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(adm)
RULE = json.loads((ROOT / "docs" / "specs" / "V8_LIQUIDITY_20261008.json").read_text())


def _panel(closes, vols):
    days = [d.date().isoformat() for d in pd.bdate_range("2022-01-03", periods=len(closes))]
    daily = pd.DataFrame({"ticker": "X", "date": days, "close": closes, "volume": vols})
    cov = pd.DataFrame({"ticker": "X", "date": days, "needed": True, "status": "ok"})
    return days, daily, cov


def test_uses_only_prior_days_and_needs_ten_days_history():
    days, daily, cov = _panel([10.0] * 12, [5e6] * 12)   # $50M/day
    p = adm.admission(daily, cov, [], RULE).set_index("date")
    assert p.loc[days[9], "reason"] == "history"         # 9 prior days
    assert p.loc[days[10], "admitted"]                   # 10 prior days
    # a huge volume on day D does not admit D itself (shifted)
    days, daily, cov = _panel([10.0] * 12, [1e5] * 11 + [1e9])
    assert not adm.admission(daily, cov, [], RULE).set_index("date").loc[days[11], "admitted"]


def test_price_floor_status_and_event_break():
    days, daily, cov = _panel([4.0] * 11 + [20.0, 20.0], [1e8] * 13)
    cov.loc[12, "status"] = "partial"
    p = adm.admission(daily, cov, [{"ticker": "X", "date": days[11]}], RULE).set_index("date")
    assert p.loc[days[10], "reason"] == "price"          # prior close $4
    assert p.loc[days[11], "reason"] == "event_break"
    assert p.loc[days[12], "reason"] == "bar_status"
