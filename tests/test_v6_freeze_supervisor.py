import json
from types import SimpleNamespace

import pytest

from scripts import run_v6_full_freeze as supervisor


@pytest.mark.parametrize("missing", ["inventory", "stores", "source", "config"])
def test_final_seal_refuses_partial_or_changed_work(tmp_path, monkeypatch, missing):
    monkeypatch.setattr(supervisor.config, "UNDERLYINGS", ["AA", "AAL"])
    monkeypatch.setattr(supervisor, "_config_record", lambda: {"campaign": "test"})
    monkeypatch.setattr(supervisor, "_source_hashes", lambda: {"source": "current"})
    inventory, output = tmp_path / "inventory", tmp_path / "ticks"
    inventory.mkdir()
    output.mkdir()
    scope = {"config": {"campaign": "test"}, "source_sha256": {"source": "current"}}
    if missing == "source":
        scope["source_sha256"] = {"source": "stale"}
    if missing == "config":
        scope["config"] = {"campaign": "different"}
    (inventory / "scope.json").write_text(json.dumps(scope))
    (inventory / "manifest.json").write_text(json.dumps({"complete": True,
        "symbols": {s: {} for s in (["AA"] if missing == "inventory" else ["AA", "AAL"])}}))
    (output / "manifest.json").write_text(json.dumps({"complete": True,
        "stores": {s: {} for s in (["AA"] if missing == "stores" else ["AA", "AAL"])}}))
    planning = SimpleNamespace(document={"symbols": {"AA": {}, "AAL": {}}})
    with pytest.raises(ValueError, match="unchanged full-universe"):
        supervisor.seal(planning, inventory, output)
    assert not (output / "final-inputs.json").exists()
