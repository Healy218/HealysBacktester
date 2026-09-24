from __future__ import annotations

import json
from pathlib import Path

import pytest

from nn_meta.v7.catalog_audit import audit_catalog, audit_store
from nn_meta.v7.storage import receipt, sha


def _sealed(path: Path, name: str, document: dict, metadata: dict) -> None:
    path.mkdir(parents=True)
    (path / name).write_text(json.dumps(document) + "\n")
    receipt(path, metadata)


def test_live_audit_reports_missing_without_readiness(tmp_path: Path) -> None:
    report = audit_catalog(tmp_path, ["A"])
    assert report["expected_stores"] == report["missing_stores"] == 3
    assert report["audited_stores"] == 0
    assert report["row_columns"] == 221
    assert report["ready_for_7_3"] is False
    with pytest.raises(ValueError, match="incomplete"):
        audit_catalog(tmp_path, ["A"], full=True)


def test_store_preflight_binds_exact_feature_and_proposal_catalog(tmp_path: Path) -> None:
    base = tmp_path / "A" / "5"
    variants = [{"strategy": "ma", "signal_minutes": 5, "params": {}, "variant_id": "one"}]
    features = base / "features"
    _sealed(features / "declaration", "declaration.json",
            {"security_id": "A", "minutes": 5, "variants": variants,
             "inputs": {"x": "hash"}, "sources": {"y": "hash"},
             "research_ready": False}, {"identity": "feature-id"})
    _sealed(features / "basis", "basis.json", {}, {"identity": "basis-id"})
    _sealed(features / "summary", "report.json",
            {"variants": 1, "full_timeframe_catalog": True,
             "source_and_input_guard": "passed", "storage_mode": "compact-v1",
             "research_ready": False},
            {"identity": "summary-id", "parent_identity": "feature-id",
             "basis_receipt_sha256": sha(features / "basis" / "complete.json")})
    proposals = base / "proposals"
    _sealed(proposals / "declaration", "declaration.json",
            {"security_id": "A", "variants": variants, "research_ready": False,
             "feature_store": str(features),
             "feature_summary_sha256": sha(features / "summary" / "complete.json")},
            {"identity": "proposal-id"})
    _sealed(proposals / "summary", "report.json",
            {"variants": 1, "entry_filter_applied": True,
             "research_ready": False, "proposals": 2},
            {"identity": "proposal-summary-id"})
    assert audit_store(base, security_id="A", minutes=5, variants=variants)["proposals"] == 2
    with pytest.raises(ValueError, match="feature scope/catalog mismatch"):
        audit_store(base, security_id="A", minutes=5, variants=[{"variant_id": "changed"}])
