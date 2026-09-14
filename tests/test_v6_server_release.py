import json
from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from nn_meta.live.v6_release import FrozenGBT, member_path, sha, verify_release
from scripts import run_v6_server as runner


@pytest.fixture
def release(tmp_path):
    root = tmp_path / "release"
    root.mkdir()
    config = {"family": "gbt", "mode": "ev", "threshold": .05, "dd_brake": None,
              "run_ids": [f"seed-{i}" for i in range(40)], "features": [f"x{i}" for i in range(164)],
              "label": "label_excess"}
    files = {"baseline_spec.json": b"{}", "model/ensemble_config.json": json.dumps(config).encode()}
    for seed in config["run_ids"]:
        for head in ("model", "magnitude"):
            files[f"model/{seed}/{head}.joblib"] = b"untrusted bytes must not be loaded before verification"
    for name, data in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    manifest = {"output_artifacts": {k.removeprefix("model/"): sha(root / k)
                                    for k in files if k.startswith("model/")},
                "baseline_spec": {"sha256": sha(root / "baseline_spec.json")}}
    (root / "model/manifest.json").write_text(json.dumps(manifest))
    doc = {"schema": "v6-server-release-v1", "model_sha256": sha(root / "model/ensemble_config.json"),
           "files": {str(p.relative_to(root)): sha(p) for p in root.rglob("*") if p.is_file()}}
    (root / "release.json").write_text(json.dumps(doc))
    return root, sha(root / "release.json")


def test_tampered_model_refused_before_unpickling(release, monkeypatch):
    root, anchor = release
    assert verify_release(root, anchor)["schema"] == "v6-server-release-v1"
    (root / "model/seed-0/model.joblib").write_bytes(b"changed")
    def unexpected(*args, **kwargs):
        raise AssertionError("unsafe model load")
    monkeypatch.setattr("joblib.load", unexpected)
    with pytest.raises(ValueError, match="release file changed"):
        FrozenGBT(root, anchor)


def test_release_anchor_and_paths_are_enforced(release, tmp_path):
    root, anchor = release
    with pytest.raises(ValueError, match="external hash"):
        verify_release(root, "0" * 64)
    with pytest.raises(ValueError, match="escapes"):
        member_path(root, "../elsewhere")
    link = root / "link"
    link.symlink_to(tmp_path)
    with pytest.raises(ValueError, match="symlinks"):
        member_path(root, "link/file")


def test_missing_features_and_infinity_cannot_score():
    model = object.__new__(FrozenGBT)
    model.features = ["one", "two"]
    model.members = []
    with pytest.raises(ValueError, match="missing"):
        model.score(pd.DataFrame({"one": [1.]}))
    with pytest.raises(ValueError, match="infinity"):
        model.score(pd.DataFrame({"one": [1.], "two": [np.inf]}))


def test_missing_snapshot_is_blocked_not_a_successful_scan(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    (state / "selftest.json").write_text(json.dumps({"status": "passed", "model_sha256": "frozen"}))
    monkeypatch.setattr(runner, "verify_release", lambda *args: {
        "campaign": "frozen", "model_sha256": "frozen", "training_inputs_sha256": "a" * 64})
    args = SimpleNamespace(state=state, release=tmp_path / "release", anchor="anchor", selftest=False,
                           snapshot_index=tmp_path / "missing.json", feed_heartbeat=None)
    # Restore process env after runner config isolation for other tests.
    for key in ("NN_META_POOL", "NN_META_CAMPAIGN", "NN_META_V6_EXPANDED", "NN_META_V6_PARITY_POLICY",
                "NN_META_V6_INPUTS", "NN_META_V6_INPUTS_SHA256"):
        monkeypatch.setenv(key, "test-before")
    result = runner.run(args, now=datetime(2026, 9, 14, 14, tzinfo=timezone.utc))
    assert result["status"] == "blocked"
    assert result["phase"] == "awaiting_live_inputs"
    assert not result["alerts_enabled"] and result["delivered"] == 0
    assert not result["live_decisions_verified"]
    assert not (state / "shadow").exists()


def test_heartbeat_never_certifies_tick_coverage(tmp_path):
    now = datetime(2026, 9, 14, 14, tzinfo=timezone.utc)
    path = tmp_path / "feed.json"
    path.write_text(json.dumps({"ts": now.isoformat(), "tick_recording": True,
        "received_quotes": 100, "trades": 2, "journal_errors": 1}))
    result = runner.inspect_feed(path, now)
    assert result["status"] == "fresh" and not result["capture_complete"]
    assert result["journal_errors"] == 1
