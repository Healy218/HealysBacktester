from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from integrations.alpaca_paper.v6_restart import prepare


NOW = datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc)


def fixture(tmp_path):
    checkout = tmp_path / "checkout"
    old = checkout / "nn_meta/live/v6_server"
    old.mkdir(parents=True)
    runtime = checkout / "scripts/run_v6_forward.py"
    runtime.parent.mkdir()
    runtime.write_text("frozen runtime\n")
    data = checkout / "data/2026-09-24"
    data.mkdir(parents=True)
    (data / "manifest.json").write_text('{"schema":"v6-inputs"}\n')
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    (old / "activation.json").write_text(json.dumps({
        "status": "passed", "broker_orders": False, "release_sha256": "a" * 64,
        "runtime_sha256": {"scripts/run_v6_forward.py": sha(runtime)},
    }))
    (old / "data-index.json").write_text(json.dumps({
        "schema": "v6-forward-data-index-v1", "release_sha256": "a" * 64,
        "path": str(data), "sha256": sha(data / "manifest.json"),
    }))
    review = tmp_path / "preflight.json"
    review.write_text(json.dumps({
        "schema": "v6-alpaca-paper-preflight-v1", "order_submission_enabled": False,
        "alpaca": {"source": "alpaca-paper-read-only", "long_option_entry_eligible": True,
                   "position_count": 0, "open_order_count": 0,
                   "open_orders_may_be_truncated": False,
                   "account_fingerprint": "b" * 64, "observed_at": NOW.isoformat()},
    }))
    return old, checkout / "nn_meta/live/v6_alpaca_paper", review


def test_restart_state_is_empty_and_bound_to_account_and_frozen_v6(tmp_path):
    old, new, review = fixture(tmp_path)
    original = (old / "activation.json").read_bytes()
    manifest = prepare(old, new, review, now=NOW)
    assert (old / "activation.json").read_bytes() == original
    assert sorted(p.name for p in new.iterdir()) == ["activation.json", "data-index.json", "paper-restart.json"]
    assert manifest["historical_positions_imported"] is False
    assert manifest["order_submission_enabled"] is False
    assert manifest["scanner_enabled"] is False
    assert manifest["account_fingerprint"] == "b" * 64
    with pytest.raises(ValueError, match="destination must be new"):
        prepare(old, new, review, now=NOW)


def test_restart_refuses_stale_or_nonempty_broker_account(tmp_path):
    old, new, review = fixture(tmp_path)
    with pytest.raises(ValueError, match="stale"):
        prepare(old, new, review, now=NOW + timedelta(hours=2))
    data = json.loads(review.read_text())
    data["alpaca"]["position_count"] = 1
    review.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="empty"):
        prepare(old, new, review, now=NOW)
    assert not new.exists()
