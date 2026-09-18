import pandas as pd
import pytest

from nn_meta.v7.noncash_admission import (
    POLICY_ID, build_exclusion_panel, compile_noncash_treatments,
    require_boundary_safe,
)
from nn_meta.v7.storage import identity


def record(kind="stock_mergers", symbol="OLD", day="2024-01-02"):
    raw = {"id": f"{kind}-{symbol}-{day}", "effective_date": day}
    return {"provider": "massive", "kind": kind, "action_id": raw["id"],
            "category": "complex", "subject_symbol": None,
            "scoped_symbols": [symbol], "effective_date": day,
            "record": raw, "record_sha256": identity(raw)}


def history():
    return pd.DataFrame({"security_id": ["sid", "sid"], "source_date": ["2024-01-01", "2024-01-02"],
        "stock_ticker": ["OLD", "OLD"], "history_admitted": [True, True]})


def test_every_record_gets_one_explicit_exclusion():
    treatments = compile_noncash_treatments([record()])
    assert len(treatments) == 1
    assert treatments[0]["policy_id"] == POLICY_ID
    assert treatments[0]["creates_cash"] is False
    assert treatments[0]["held_position_treatment"] == "reject_crossing_position"


def test_boundary_exclusion_is_consumed_by_history_panel():
    panel = build_exclusion_panel(history(), [record()], compile_noncash_treatments([record()]))
    assert panel.loc[panel.source_date == "2024-01-02", "noncash_boundary_excluded"].item()
    assert not panel.loc[panel.source_date == "2024-01-02", "history_admitted"].item()
    assert panel.loc[panel.source_date == "2024-01-01", "history_admitted"].item()


def test_boundary_guard_rejects_crossing_position():
    panel = build_exclusion_panel(history(), [record()], compile_noncash_treatments([record()]))
    with pytest.raises(ValueError, match="excluded noncash boundary"):
        require_boundary_safe(panel, security_id="sid", source_dates=["2024-01-02"])


def test_boundary_guard_allows_pre_boundary_history():
    panel = build_exclusion_panel(history(), [record()], compile_noncash_treatments([record()]))
    selected = require_boundary_safe(panel, security_id="sid", source_dates=["2024-01-01"])
    assert len(selected) == 1
