"""V8.0-pit driver: root hygiene applied before reconstitution."""
import importlib.util
from pathlib import Path

import pandas as pd

_SPEC = importlib.util.spec_from_file_location(
    "build_v8_universe_pit",
    Path(__file__).resolve().parent.parent / "scripts" / "build_v8_universe_pit.py")
v8pit = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(v8pit)


def _rows(*triples):
    return pd.DataFrame([{"root": r, "date": d, "opt_dollar_vol": v}
                         for r, d, v in triples])


def test_test_roots_dropped():
    out = v8pit.apply_aliases(_rows(("ATEST", "2022-01-03", 1e7),
                                    ("AAPL", "2022-01-03", 1e8)), {})
    assert list(out["root"]) == ["AAPL"]


def test_rekey_before_seam_then_alias():
    # META root belonged to an ETF before FB took the symbol on 2022-06-09
    out = v8pit.apply_aliases(
        _rows(("META", "2022-06-08", 1.0), ("FB", "2022-06-08", 100.0),
              ("META", "2022-06-09", 120.0)),
        {"FB": "META"}, [("META", "2022-06-09", "METV")])
    assert list(out["root"]) == ["METV", "META", "META"]


def test_alias_chain_resolves_to_current_ticker():
    out = v8pit.apply_aliases(
        _rows(("VIAC", "2022-02-16", 1.0), ("PARA", "2024-01-02", 1.0),
              ("PSKY", "2025-08-08", 1.0)),
        {"VIAC": "PARA", "PARA": "PSKY"})
    assert set(out["root"]) == {"PSKY"}


def test_weekday_gaps_lists_missing_weekdays():
    assert v8pit.weekday_gaps(["2025-01-08", "2025-01-10"]) == ["2025-01-09"]
