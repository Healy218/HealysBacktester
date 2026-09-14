import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from integrations.dashboard.v6_followup import append_followup


def fixture(tmp_path):
    model = tmp_path / "nn_meta/campaigns/test/v6/model_final/ensemble_config.json"
    model.parent.mkdir(parents=True); model.write_text('{"family":"gbt"}')
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    base = tmp_path / "validation"; base.mkdir()
    result = {"complete": True, "research_only": True, "scanner_promotion": False,
        "limitations": ["Not a fresh holdout"], "policies": {side: {"aggregate": {
            "retained_fills": {"costs": {"base": {"n_positions": 4, "total_return": .1,
                "max_drawdown": .05, "independent_ledger_match": True}}}}} for side in ["candidate", "baseline"]}}
    (base / "results.json").write_text(json.dumps(result))
    (base / "scope.json").write_text(json.dumps({"inputs": {str(model): digest}}))
    (base / "complete.json").write_text(json.dumps({"outputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                                                  for p in base.iterdir()}}))
    shadow = tmp_path / "shadow"; shadow.mkdir()
    (shadow / "summary.json").write_text(json.dumps({"schema": "v6-shadow-summary-v1", "research_only": True,
        "scanner_promotion": False, "bundle_sha256": digest, "signals": 5, "candidate_selections": 2,
        "baseline_selections": 3, "quote_observations": 0, "failed_passes": 1, "last_pass_at": "2026-09-13T12:00:00Z",
        "execution_status": "awaiting quotes", "limitations": ["Signals are not positions"]}))
    return base, shadow


def report():
    return {"campaign": "test", "tables": [], "sources": [], "notes": []}


def test_followup_tables_keep_revalidation_and_unrealized_shadow_distinct(tmp_path):
    execution, shadow = fixture(tmp_path)
    value = append_followup(tmp_path, report(), execution=execution, shadow=shadow,
                            now=datetime(2026,9,13,12,1,tzinfo=timezone.utc))
    assert len(value["tables"]) == 2
    assert len(value["tables"][0]["rows"]) == 2
    assert value["tables"][0]["rows"][0][4] == "+10.0%"
    assert "not a fresh holdout" in value["tables"][0]["note"]
    assert value["tables"][1]["rows"][0][1] == "Recording · research only"
    assert not any("return" in str(r).lower() for r in value["tables"][1]["rows"])


def test_followup_refuses_corruption_wrong_campaign_and_outside_paths(tmp_path):
    execution, shadow = fixture(tmp_path)
    with pytest.raises(ValueError, match="different training campaign"):
        append_followup(tmp_path, dict(report(), campaign="other"), execution=execution)
    (execution / "results.json").write_text('{}')
    with pytest.raises(ValueError, match="receipt"):
        append_followup(tmp_path, report(), execution=execution)
    with pytest.raises(ValueError, match="inside"):
        append_followup(tmp_path, report(), shadow=tmp_path.parent)


def test_shadow_freshness_and_model_binding(tmp_path):
    _, shadow = fixture(tmp_path)
    result = append_followup(tmp_path, report(), shadow=shadow, now=datetime(2026,9,14,tzinfo=timezone.utc))
    assert result["tables"][0]["rows"][0][1] == "Stale / no recent pass"
    path = shadow / "summary.json"
    value = json.loads(path.read_text()); value["bundle_sha256"] = "wrong"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="different model"):
        append_followup(tmp_path, report(), shadow=shadow)
