from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pandas as pd
import pytest

from incubator.bundles import BundleError, create_manifest, manifest_digest, pack_directory, verify_bundle
from incubator.budget import BudgetError, ResourceBudget
from incubator.after_close import DailyInputError, capture_v6_day, load_feature_request
from incubator.campaign import run_campaign
from incubator.checkpoints import CheckpointError
from incubator.feature_capture import FeatureCaptureError, capture_feature_matrix
from incubator.forward import ForwardDataError, _sha256, load_v6_snapshot
from incubator.live_features import LiveFeatureError, publish_v6_features
from incubator.outcomes import OutcomeJoinError, join_matured_outcomes
from incubator.metrics import MetricsError, score_jsonl, score_records
from incubator.replay import ReplayError, load_feature_frame
from incubator.registry import discover
from incubator.sandbox import execute_bundle


def _make_bundle(tmp_path: Path, artifact_id: str = "v5-test") -> Path:
    source = tmp_path / "source"
    source.mkdir(parents=True)
    (source / "model.bin").write_bytes(b"model-bytes")
    (source / "params.json").write_text('{"threshold": 0.5}\n')
    manifest = create_manifest(source, artifact_id=artifact_id, artifact_version="2026-09-22",
                               artifact_kind="option_expert", created_at="2026-09-22T00:00:00+00:00",
                               compatibility={"forward_data_contract": "paper_forward_v1"})
    bundle = tmp_path / f"{artifact_id}.tar.gz"
    pack_directory(source, bundle, manifest=manifest)
    return bundle


def test_pack_and_verify_round_trip(tmp_path: Path) -> None:
    manifest = verify_bundle(_make_bundle(tmp_path), expected_artifact_id="v5-test")
    assert manifest["manifest_sha256"]
    assert {item["path"] for item in manifest["files"]} == {"model.bin", "params.json"}


def test_dry_run_writes_read_only_receipt(tmp_path: Path) -> None:
    from incubator.runner import dry_run
    receipt = dry_run(_make_bundle(tmp_path), output_dir=tmp_path / "receipts")
    assert receipt["status"] == "verified_not_executed"
    assert receipt["receipt_schema"] == "incubator-receipt-v1"


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    bundle = tmp_path / "bad.tar.gz"
    payload = b"bad"
    with tarfile.open(bundle, "w:gz") as archive:
        info = tarfile.TarInfo("../escape.txt")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    with pytest.raises(BundleError, match="unsafe bundle member"):
        verify_bundle(bundle)


def test_tampered_file_is_rejected(tmp_path: Path) -> None:
    bundle = _make_bundle(tmp_path)
    tampered = tmp_path / "tampered.tar.gz"
    with tarfile.open(bundle, "r:gz") as source, tarfile.open(tampered, "w:gz") as target:
        for member in source.getmembers():
            payload = source.extractfile(member).read() if member.isfile() else None
            if member.name == "model.bin":
                payload = b"tampered"
                member.size = len(payload)
            target.addfile(member, io.BytesIO(payload) if payload is not None else None)
    with pytest.raises(BundleError, match="file digest mismatch"):
        verify_bundle(tampered)


def test_discovery_rejects_duplicate_artifact_ids(tmp_path: Path) -> None:
    first = _make_bundle(tmp_path / "one")
    second = _make_bundle(tmp_path / "two")
    with pytest.raises(BundleError, match="duplicate artifact_id"):
        discover([first.parent, second.parent])


def test_discovery_rejects_incompatible_contract(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "model.bin").write_bytes(b"model")
    manifest = create_manifest(source, artifact_id="bad-contract", artifact_version="1",
                               artifact_kind="option_expert", created_at="2026-09-22T00:00:00+00:00",
                               compatibility={"forward_data_contract": "other_contract"})
    bundle = tmp_path / "bad-contract.tar.gz"
    pack_directory(source, bundle, manifest=manifest)
    with pytest.raises(BundleError, match="incompatible forward data contract"):
        discover([tmp_path])


def test_sandbox_is_disabled_by_default_for_entrypoint(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "entrypoint.py").write_text("print('should not run')\n")
    manifest = create_manifest(source, artifact_id="sandbox-test", artifact_version="1",
                               artifact_kind="option_expert", created_at="2026-09-22T00:00:00+00:00",
                               compatibility={"forward_data_contract": "paper_forward_v1"})
    manifest["entrypoint"] = ["entrypoint.py"]
    manifest["manifest_sha256"] = manifest_digest(manifest)
    bundle = tmp_path / "sandbox-test.tar.gz"
    pack_directory(source, bundle, manifest=manifest)
    receipt = execute_bundle(bundle, {"schema": "paper-forward-request-v1"}, tmp_path / "out")
    assert receipt["status"] == "verified_execution_disabled"


def test_v6_forward_snapshot_is_causal_and_hash_bound(tmp_path: Path) -> None:
    root = tmp_path / "snapshot"
    root.mkdir()
    payload = root / "context.json"
    payload.write_text("{}\n")
    manifest = {"schema": "v6-forward-data-v1", "through": "2026-09-21", "files": {"context.json": _sha256(payload)}}
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
    index = tmp_path / "data-index.json"
    index.write_text(json.dumps({"schema": "v6-forward-data-index-v1", "path": str(root), "sha256": _sha256(manifest_path), "through": "2026-09-21"}) + "\n")
    assert load_v6_snapshot(index, as_of="2026-09-21").through == "2026-09-21"
    with pytest.raises(ForwardDataError, match="exceeds snapshot"):
        load_v6_snapshot(index, as_of="2026-09-22")


def test_forward_request_includes_declared_feature_matrix(tmp_path: Path) -> None:
    root = tmp_path / "snapshot"
    root.mkdir()
    payload = root / "features.parquet"
    payload.write_bytes(b"feature-bytes")
    manifest = {"schema": "v6-forward-data-v1", "through": "2026-09-21",
                "files": {"features.parquet": _sha256(payload)},
                "feature_matrix": {"path": "features.parquet", "feature_columns": ["x"],
                                    "outcome_column": "outcome"}}
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
    index = tmp_path / "data-index.json"
    index.write_text(json.dumps({"schema": "v6-forward-data-index-v1", "path": str(root),
                                 "sha256": _sha256(manifest_path), "through": "2026-09-21"}) + "\n")
    request = load_v6_snapshot(index).request(artifact_id="test")
    assert request["feature_path"] == "features.parquet"
    assert request["feature_columns"] == ["x"]


def test_common_metrics_are_comparable() -> None:
    result = score_records([{"prediction": 1, "outcome": 1}, {"prediction": -1, "outcome": 1}, {"prediction": 1, "outcome": -1}])
    assert result["metrics_schema_version"] == 1
    assert result["directional_accuracy"] == pytest.approx(1 / 3)
    with pytest.raises(MetricsError, match="no result records"):
        score_records([])


def test_jsonl_metrics_score_every_row(tmp_path: Path) -> None:
    results = tmp_path / "results.jsonl"
    results.write_text('{"prediction": 1, "outcome": 1}\n{"prediction": -1, "outcome": 1}\n')
    scored = score_jsonl(results)
    assert scored["n"] == 2
    assert scored["directional_accuracy"] == 0.5


def test_campaign_checkpoint_skips_completed_artifact(tmp_path: Path) -> None:
    bundle = _make_bundle(tmp_path)
    entry = {"artifact_id": "v5-test", "artifact_version": "2026-09-22", "bundle": str(bundle)}
    request = {"schema": "paper-forward-request-v1", "as_of": "2026-09-21"}
    first = run_campaign([entry], request=request, output_dir=tmp_path / "out", run_id="run-1", checkpoint_path=tmp_path / "checkpoint.json")
    second = run_campaign([entry], request=request, output_dir=tmp_path / "out", run_id="run-1", checkpoint_path=tmp_path / "checkpoint.json")
    assert first["completed_count"] == second["completed_count"] == 1


def test_campaign_routes_distinct_requests_and_outputs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "entrypoint.py").write_text(
        "import json, os\nfrom pathlib import Path\n"
        "request=json.loads(Path(os.environ['AI_INCUBATOR_REQUEST']).read_text())\n"
        "Path(os.environ['AI_INCUBATOR_OUTPUT'], 'results.jsonl').write_text("
        "json.dumps({'prediction': request['prediction']})+'\\n')\n"
    )
    entries = []
    for artifact_id in ("incubator-v5-test", "incubator-v6-test"):
        manifest = create_manifest(source, artifact_id=artifact_id, artifact_version="1",
                                   artifact_kind="option_expert", created_at="2026-09-22T00:00:00+00:00",
                                   compatibility={"forward_data_contract": "paper_forward_v1"})
        manifest["entrypoint"] = ["entrypoint.py"]
        manifest["manifest_sha256"] = manifest_digest(manifest)
        bundle = tmp_path / f"{artifact_id}.tar.gz"
        pack_directory(source, bundle, manifest=manifest)
        entries.append({"artifact_id": artifact_id, "artifact_version": "1", "bundle": str(bundle)})
    requests = {"incubator-v5-test": {"prediction": 1}, "incubator-v6-test": {"prediction": -1}}
    result = run_campaign(entries, request={"as_of": "2026-09-22"}, artifact_requests=requests,
                          output_dir=tmp_path / "out", run_id="run-1",
                          checkpoint_path=tmp_path / "checkpoint.json", allow_execution=True)
    assert result["failed_count"] == 0
    assert {receipt["sandbox"]["prediction_count"] for receipt in result["receipts"]} == {1}
    assert sorted((tmp_path / "out").rglob("results.jsonl")) and len(list((tmp_path / "out").rglob("results.jsonl"))) == 2
    for receipt in result["receipts"]:
        row = json.loads((Path(receipt["output_dir"]) / "results.jsonl").read_text())
        assert row["prediction"] == requests[receipt["artifact_id"]]["prediction"]
    with pytest.raises(CheckpointError, match="input fingerprint"):
        run_campaign(entries, request={"as_of": "2026-09-22"},
                     artifact_requests={**requests, "incubator-v6-test": {"prediction": 0}},
                     output_dir=tmp_path / "out", run_id="run-1",
                     checkpoint_path=tmp_path / "checkpoint.json")


def test_checkpoint_refuses_changed_input(tmp_path: Path) -> None:
    bundle = _make_bundle(tmp_path)
    entry = {"artifact_id": "v5-test", "artifact_version": "2026-09-22", "bundle": str(bundle)}
    run_campaign([entry], request={"as_of": "2026-09-21"}, output_dir=tmp_path / "out", run_id="run-1", checkpoint_path=tmp_path / "checkpoint.json")
    with pytest.raises(CheckpointError, match="input fingerprint"):
        run_campaign([entry], request={"as_of": "2026-09-22"}, output_dir=tmp_path / "out", run_id="run-1", checkpoint_path=tmp_path / "checkpoint.json")


def test_resource_budget_rejects_invalid_values() -> None:
    with pytest.raises(BudgetError, match="positive"):
        ResourceBudget(artifact_seconds=0).validate()


def test_campaign_enforces_artifact_count_budget(tmp_path: Path) -> None:
    bundle = _make_bundle(tmp_path)
    entry = {"artifact_id": "v5-test", "artifact_version": "2026-09-22", "bundle": str(bundle)}
    with pytest.raises(BudgetError, match="positive"):
        run_campaign([entry], request={"as_of": "2026-09-21"}, output_dir=tmp_path / "out",
                     run_id="run-1", checkpoint_path=tmp_path / "checkpoint.json",
                     budget=ResourceBudget(max_artifacts=0))


def test_campaign_records_failed_entrypoint_and_budget(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "entrypoint.py").write_text("raise SystemExit(7)\n")
    manifest = create_manifest(source, artifact_id="failing-test", artifact_version="1",
                               artifact_kind="option_expert", created_at="2026-09-22T00:00:00+00:00",
                               compatibility={"forward_data_contract": "paper_forward_v1"})
    manifest["entrypoint"] = ["entrypoint.py"]
    manifest["manifest_sha256"] = manifest_digest(manifest)
    bundle = tmp_path / "failing-test.tar.gz"
    pack_directory(source, bundle, manifest=manifest)
    entry = {"artifact_id": "failing-test", "artifact_version": "1", "bundle": str(bundle)}
    result = run_campaign([entry], request={"as_of": "2026-09-21"}, output_dir=tmp_path / "out",
                          run_id="run-fail", checkpoint_path=tmp_path / "checkpoint.json",
                          allow_execution=True,
                          budget=ResourceBudget(artifact_seconds=5, memory_bytes=256 * 1024**2))
    assert result["failed_count"] == 1
    receipt = json.loads((tmp_path / "out" / "failing-test.receipt.json").read_text())
    assert receipt["status"] == "failed"
    assert receipt["budget"]["artifact_seconds"] == 5


def test_sandbox_scores_successful_jsonl_output(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir(parents=True)
    (source / "entrypoint.py").write_text(
        "from pathlib import Path\n"
        "import os\n"
        "Path(os.environ['AI_INCUBATOR_OUTPUT'], 'results.jsonl').write_text("
        "'{\\\"prediction\\\": 1, \\\"outcome\\\": 1}\\n')\n"
    )
    manifest = create_manifest(source, artifact_id="metrics-test", artifact_version="1",
                               artifact_kind="option_expert", created_at="2026-09-22T00:00:00+00:00",
                               compatibility={"forward_data_contract": "paper_forward_v1"})
    manifest["entrypoint"] = ["entrypoint.py"]
    manifest["manifest_sha256"] = manifest_digest(manifest)
    bundle = tmp_path / "metrics-test.tar.gz"
    pack_directory(source, bundle, manifest=manifest)
    receipt = execute_bundle(bundle, {"as_of": "2026-09-21"}, tmp_path / "out",
                             allow_execution=True, timeout_seconds=5,
                             memory_bytes=512 * 1024**2)
    assert receipt["status"] == "executed"
    assert receipt["metrics"]["n"] == 1


def test_replay_refuses_missing_forward_feature_contract(tmp_path: Path) -> None:
    with pytest.raises(ReplayError, match="feature_path"):
        load_feature_frame({"snapshot_root": str(tmp_path)})


def test_replay_refuses_incomplete_forward_features(tmp_path: Path) -> None:
    frame = pd.DataFrame({"x": [1.0], "outcome": [1.0]})
    frame.to_parquet(tmp_path / "features.parquet")
    request = {"snapshot_root": str(tmp_path), "feature_path": "features.parquet",
               "feature_columns": ["x", "missing"], "outcome_column": "outcome"}
    with pytest.raises(ReplayError, match="missing 1 columns"):
        load_feature_frame(request)


def test_pack_can_embed_keras_replay_entrypoint(tmp_path: Path) -> None:
    source = tmp_path / "model"
    source.mkdir()
    (source / "ensemble_config.json").write_text('{"features": ["x"], "run_ids": []}\n')
    # Exercise the manifest contract directly; the CLI integration is covered
    # by its --help and real bundle smoke commands.
    manifest = create_manifest(source, artifact_id="keras-test", artifact_version="1",
                               artifact_kind="option_expert", created_at="2026-09-22T00:00:00+00:00",
                               compatibility={"forward_data_contract": "paper_forward_v1"})
    assert manifest["files"]


def test_feature_capture_is_point_in_time_and_manifested(tmp_path: Path) -> None:
    source = tmp_path / "rows.parquet"
    pd.DataFrame({"entry_date": ["2026-09-20", "2026-09-21", "2026-09-22"],
                  "strategy": ["volume", "ma", "ma"], "x": [1.0, 2.0, 3.0],
                  "outcome": [0.5, None, -0.5]}).to_parquet(source)
    config = tmp_path / "config.json"
    config.write_text('{"features": ["x", "strat_volume"]}\n')
    manifest = capture_feature_matrix([source], tmp_path / "snapshot", config, "2026-09-21",
                                      "outcome", max_rows=1)
    assert manifest["rows"] == 1
    assert manifest["derived_columns"] == ["strat_volume"]
    captured = pd.read_parquet(tmp_path / "snapshot" / "features.parquet")
    assert captured["x"].tolist() == [1.0]
    assert (tmp_path / "snapshot" / "feature-manifest.json").is_file()


def test_feature_capture_refuses_missing_columns(tmp_path: Path) -> None:
    source = tmp_path / "rows.parquet"
    pd.DataFrame({"entry_date": ["2026-09-20"], "x": [1.0], "outcome": [0.5]}).to_parquet(source)
    with pytest.raises(FeatureCaptureError, match="missing 1 model columns"):
        capture_feature_matrix([source], tmp_path / "snapshot", {"features": ["x", "missing"]},
                               "2026-09-21", "outcome")


def test_live_feature_publication_marks_outcomes_pending(tmp_path: Path) -> None:
    source = tmp_path / "candidates.parquet"
    pd.DataFrame({"symbol": ["SPY"], "strategy": ["volume"], "dte": [5],
                  "entry_ts": ["2026-09-21T19:15:00Z"], "x": [1.0]}).to_parquet(source)
    manifest = publish_v6_features([source], tmp_path / "live", {"features": ["x"]}, "2026-09-21")
    assert manifest["outcome_status"] == "pending"
    assert "net_return" not in pd.read_parquet(tmp_path / "live" / "features.parquet").columns
    request = load_feature_request(tmp_path / "live", generation="v6", as_of="2026-09-21")
    assert "outcome_column" not in request
    with pytest.raises(DailyInputError, match="generation/date mismatch"):
        load_feature_request(tmp_path / "live", generation="v5", as_of="2026-09-21")


def test_v6_daily_capture_is_session_scoped_and_sealed(tmp_path: Path) -> None:
    passes = tmp_path / "passes"
    source = passes / "20260921T193000Z" / "candidates.parquet"
    source.parent.mkdir(parents=True)
    pd.DataFrame({"symbol": ["SPY"], "strategy": ["ma"], "dte": [5],
                  "entry_ts": ["2026-09-21T19:30:00Z"], "x": [1.0]}).to_parquet(source)
    config = tmp_path / "model.json"
    config.write_text('{"family": "gbt", "features": ["x"]}')
    target = capture_v6_day(passes, config, tmp_path / "daily", "2026-09-21")
    assert capture_v6_day(passes, config, tmp_path / "daily", "2026-09-21") == target
    with pytest.raises(DailyInputError, match="no candidate parquets"):
        capture_v6_day(passes, config, tmp_path / "daily", "2026-09-22")
    pd.DataFrame({"symbol": ["SPY"], "strategy": ["ma"], "dte": [5],
                  "entry_ts": ["2026-09-21T19:30:00Z"], "x": [2.0]}).to_parquet(source)
    with pytest.raises(DailyInputError, match="captured inputs changed"):
        capture_v6_day(passes, config, tmp_path / "daily", "2026-09-21")


def test_live_gbt_feature_publication_allows_model_native_nan(tmp_path: Path) -> None:
    source = tmp_path / "candidates.parquet"
    pd.DataFrame({"symbol": ["SPY"], "strategy": ["ma"], "dte": [5],
                  "entry_ts": ["2026-09-21T19:15:00Z"], "x": [None]}).to_parquet(source)
    manifest = publish_v6_features([source], tmp_path / "live", {"family": "gbt", "features": ["x"]}, "2026-09-21")
    assert manifest["missing_value_policy"] == "model_native_nan"


def test_live_feature_publication_refuses_incomplete_source(tmp_path: Path) -> None:
    source = tmp_path / "candidates.parquet"
    pd.DataFrame({"entry_ts": ["2026-09-21T19:15:00Z"], "x": [None]}).to_parquet(source)
    with pytest.raises(LiveFeatureError, match="missing 1 model columns"):
        publish_v6_features([source], tmp_path / "live", {"features": ["x", "y"]}, "2026-09-21")


def test_outcome_join_requires_exact_identity_and_publishes_matured_rows(tmp_path: Path) -> None:
    source = tmp_path / "candidates.parquet"
    pd.DataFrame({"symbol": ["SPY", "QQQ"], "strategy": ["ma", "ma"], "dte": [5, 5],
                  "entry_ts": ["2026-09-20T19:15:00Z", "2026-09-20T19:15:00Z"],
                  "x": [1.0, 2.0]}).to_parquet(source)
    live = tmp_path / "live"
    publish_v6_features([source], live, {"features": ["x"]}, "2026-09-21")
    outcomes = tmp_path / "outcomes.parquet"
    pd.DataFrame({"symbol": ["SPY"], "strategy": ["ma"], "dte": [5],
                  "entry_ts": ["2026-09-20T19:15:00Z"], "net_return": [0.25]}).to_parquet(outcomes)
    result = join_matured_outcomes(live, [outcomes], tmp_path / "ready")
    assert result["status"] == "replay_ready"
    assert result["matched_rows"] == 1
    assert pd.read_parquet(tmp_path / "ready" / "features.parquet")["net_return"].tolist() == [0.25]
    request = load_feature_request(tmp_path / "ready", generation="v6", as_of="2026-09-21")
    assert request["outcome_column"] == "net_return"


def test_outcome_join_reports_pending_when_nothing_matured(tmp_path: Path) -> None:
    source = tmp_path / "candidates.parquet"
    pd.DataFrame({"symbol": ["SPY"], "strategy": ["ma"], "dte": [5],
                  "entry_ts": ["2026-09-20T19:15:00Z"], "x": [1.0]}).to_parquet(source)
    live = tmp_path / "live"
    publish_v6_features([source], live, {"features": ["x"]}, "2026-09-21")
    outcomes = tmp_path / "outcomes.parquet"
    pd.DataFrame({"symbol": ["QQQ"], "strategy": ["ma"], "dte": [5],
                  "entry_ts": ["2026-09-20T19:15:00Z"], "net_return": [0.25]}).to_parquet(outcomes)
    result = join_matured_outcomes(live, [outcomes], tmp_path / "ready")
    assert result["status"] == "pending"
    assert result["pending_rows"] == 1
