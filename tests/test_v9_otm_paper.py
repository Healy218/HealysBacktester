import importlib.util
import sys

import pandas as pd

spec = importlib.util.spec_from_file_location("run_v9_otm_paper", "scripts/run_v9_otm_paper.py")
p = importlib.util.module_from_spec(spec)
sys.modules["run_v9_otm_paper"] = p
spec.loader.exec_module(p)

DAYS = ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22"]


def test_entry_reaction_by_session():
    assert p.entry_reaction("2026-10-20", "amc", DAYS) == ("2026-10-20", "2026-10-21")
    assert p.entry_reaction("2026-10-20", "bmo", DAYS) == ("2026-10-19", "2026-10-20")
    assert p.entry_reaction("2026-10-20", "", DAYS) is None
    assert p.entry_reaction("2026-10-25", "amc", DAYS) is None


def test_usual_session_needs_a_clear_majority():
    f = pd.DataFrame({"ticker": "X", "form": "8-K", "items": "2.02",
                      "acceptance_utc": ["2026-01-28T21:05:00Z", "2026-04-29T20:05:00Z",
                                         "2026-07-29T20:06:00Z", "2025-10-29T20:07:00Z"]})
    assert p.usual_session("X", f) == "amc"
    f.loc[0:1, "acceptance_utc"] = ["2026-01-28T12:00:00Z", "2026-04-29T11:00:00Z"]
    assert p.usual_session("X", f) is None
