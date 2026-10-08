"""V8 contract verification refuses missing or changed artifacts."""
import json

import pytest

from nn_meta import v8_contract as vc


def test_verify_detects_change(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "REPO", tmp_path)
    art = tmp_path / "a.json"
    art.write_text("{}")
    contract = tmp_path / "c.json"
    contract.write_text(json.dumps({"artifacts": {"a": vc.describe(art)}}))
    vc.verify(contract)
    art.write_text('{"x": 1}')
    with pytest.raises(vc.ContractError, match="sha256 changed"):
        vc.verify(contract)
    art.unlink()
    with pytest.raises(vc.ContractError, match="missing"):
        vc.verify(contract)
