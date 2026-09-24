import json

import pandas as pd
import pytest

from nn_meta.v7.catalog_reuse import (check_admitted_actions, compatible_security,
                                      source_compatible)


def test_reuse_rejects_changed_computation_source():
    assert source_compatible({"producer.py": "same"}, {"producer.py": "same"})
    assert not source_compatible({"producer.py": "same"}, {"producer.py": "changed"})
    assert not source_compatible({"producer.py": "same"},
                                 {"producer.py": "same", "new_signal.py": "new"})


def test_reuse_allows_exact_review_additions_but_checks_their_bound_bytes():
    from nn_meta.v7.catalog_reuse import ROOT
    review = str(ROOT / "docs/specs/V7_LAST45_DATED_NONCASH_20260924.json")
    checker = str(ROOT / "nn_meta/v7/catalog_reuse.py")
    assert source_compatible({"producer.py": "same", checker: "old"},
                             {"producer.py": "same", checker: "new", review: "sealed"})
    assert not source_compatible({"producer.py": "same", review: "old"},
                                 {"producer.py": "same", review: "changed"})
    assert not source_compatible({"producer.py": "same"},
                                 {"producer.py": "same", "unknown_review.json": "new"})


def test_action_coverage_preflight_rejects_mixed_frozen_parents(tmp_path):
    history, actions, coverage = (tmp_path / name for name in ("history", "actions", "coverage"))
    for path in (history, actions, coverage):
        path.mkdir()
    pd.DataFrame([{"security_id": "S", "source_date": "2022-03-15",
                   "source_status": "observed"}]).to_parquet(history / "history.parquet")
    pd.DataFrame([{"security_id": "S", "source_date": "2022-03-15",
                   "history_admitted": True, "event_id": "new-event"}]).to_parquet(coverage / "coverage.parquet")
    (coverage / "complete.json").write_text("sealed")
    (actions / "actions.json").write_text(json.dumps([{"security_id": "S", "action": {
        "event_id": "new-event", "effective_at": "2022-03-15T13:30:00+00:00"}}]))
    assert check_admitted_actions(history, actions, coverage)["admitted_events"] == 1
    (actions / "actions.json").write_text(json.dumps([{"security_id": "S", "action": {
        "event_id": "old-event", "effective_at": "2022-03-15T13:30:00+00:00"}}]))
    with pytest.raises(ValueError, match="Action/coverage preflight mismatch"):
        check_admitted_actions(history, actions, coverage)


def test_reuse_requires_original_action_and_current_coverage_receipts(tmp_path, monkeypatch):
    from nn_meta.v7 import catalog_reuse
    for minutes in (5, 15, 30):
        base = tmp_path / "S" / str(minutes)
        (base / "features/declaration").mkdir(parents=True)
        (base / "proposals/summary").mkdir(parents=True)
        (base / "proposals/summary/complete.json").write_text("sealed")
        (base / "features/declaration/declaration.json").write_text(json.dumps({
            "inputs": {"/f/v7-ordinary-actions-20260918-7-2-current/actions.json": "old"},
            "action_coverage": {"receipt_sha256": "current"},
            "actions": [], "start": "2022-03-15T04:00:00+00:00",
            "end": "2022-03-16T04:00:00+00:00"}))
    monkeypatch.setattr(catalog_reuse, "source_compatible", lambda *args: True)
    monkeypatch.setattr(catalog_reuse, "audit_store", lambda *args, **kwargs: {
        "feature_receipt_sha256": "feature", "proposal_receipt_sha256": "proposal"})
    variants = {minutes: [] for minutes in (5, 15, 30)}
    assert len(compatible_security(tmp_path, "S", [], old_action_sha="old",
                                   coverage_sha="current", variants=variants)) == 3
    assert compatible_security(tmp_path, "S", [], old_action_sha="wrong",
                               coverage_sha="current", variants=variants) is None
    assert compatible_security(tmp_path, "S", [], old_action_sha="old",
                               coverage_sha="wrong", variants=variants) is None
