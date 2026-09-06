"""Campaign isolation and launcher refusal tests; no providers/training jobs."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from scripts import research_local as runner

ROOT = Path(__file__).resolve().parents[1]


def config_snapshot(pool, campaign):
    code = """import json
from nn_meta import config as c
print(json.dumps({k: str(getattr(c,k)) for k in
('DATA_CACHE','ARTIFACTS','RUNS_DIR','REPORTS_DIR','MODEL_FINAL_DIR','V4_MODEL_FINAL_DIR')}))
"""
    env = dict(os.environ, NN_META_POOL=pool, NN_META_CAMPAIGN=campaign,
               PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                            capture_output=True, text=True)
    return result


@pytest.mark.parametrize("bad", ["../old", "/tmp/out", "a/b", ".", "a b", "a\nb", "x" * 65])
def test_unsafe_campaign_fails_before_config_outputs(bad):
    result = config_snapshot("v5", bad)
    assert result.returncode != 0
    assert "simple 1–64 character name" in result.stderr


def test_named_outputs_and_legacy_bundle_defaults_remain_separate():
    named = json.loads(config_snapshot("v6", "audit-check").stdout.splitlines()[-1])
    legacy = json.loads(config_snapshot("v31", "").stdout.splitlines()[-1])
    wide = json.loads(config_snapshot("v5", "").stdout.splitlines()[-1])
    base = ROOT / "nn_meta" / "campaigns" / "audit-check" / "v6"
    for key, kind in (("ARTIFACTS", "artifacts"), ("RUNS_DIR", "runs"),
                      ("REPORTS_DIR", "reports"), ("MODEL_FINAL_DIR", "model_final"),
                      ("V4_MODEL_FINAL_DIR", "model_final")):
        assert named[key] == str(base / kind)
    assert named["DATA_CACHE"] == str(ROOT / "nn_meta" / "data_cache_v5")
    assert legacy["V4_MODEL_FINAL_DIR"] == str(ROOT / "nn_meta" / "model_final_v4")
    assert wide["V4_MODEL_FINAL_DIR"] == str(ROOT / "nn_meta" / "model_final_v5")


def test_cross_pool_reuse_never_falls_back_to_historical_rows(tmp_path, monkeypatch):
    from nn_meta import config, build_meta_dataset as builder
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "CAMPAIGN", "new-run")
    monkeypatch.setattr(config, "POOL", "v6")
    entry = {"strategies": {"ma": {"params": {"fast_window": 2, "slow_window": 4}, "dte": 5}}}
    rows = pd.DataFrame({"symbol": ["SPY"] * 5, "strategy": ["ma"] * 5,
                         "dte": [1, 5, 10, 30, 45], "executed": [True] * 5})

    def write_fixture(base):
        (base / "meta_rows").mkdir(parents=True)
        (base / "baseline_spec.json").write_text(json.dumps({"symbols": {"SPY": entry}}))
        path = base / "meta_rows" / "SPY.parquet"
        rows.to_parquet(path)
        builder._write_provenance(path, builder._provenance(entry, rows.dte.tolist()))

    write_fixture(tmp_path / "artifacts_v5")
    assert builder._reusable_rows("SPY", entry, "v5", False) is None
    write_fixture(tmp_path / "campaigns" / "different-run" / "v5" / "artifacts")
    assert builder._reusable_rows("SPY", entry, "v5", False) is None
    write_fixture(config.output_dir("artifacts", "v5"))
    actual, _ = builder._reusable_rows("SPY", entry, "v5", False)
    pd.testing.assert_frame_equal(actual, rows)


@pytest.fixture
def campaign(tmp_path):
    root = tmp_path / "repo" / "nn_meta"
    base = root / "campaigns" / "pilot" / "v6"
    (root / "data_cache_v5").mkdir(parents=True)
    (root / "data_cache_v5" / "contracts.parquet").write_bytes(b"raw-input-A")
    return SimpleNamespace(ROOT=root, POOL="v6", CAMPAIGN="pilot",
                           DATA_CACHE=root / "data_cache_v5", ARTIFACTS=base / "artifacts",
                           RUNS_DIR=base / "runs", REPORTS_DIR=base / "reports",
                           MODEL_FINAL_DIR=base / "model_final", V4_MODEL_FINAL_DIR=base / "model_final",
                           WINDOW_START="2025-03-28", WINDOW_END="2025-04-01",
                           UNDERLYINGS=["SPY", "QQQ"], PROPOSAL_STRATEGIES=["ma"])


def test_preview_is_explicit_read_only_and_cwd_independent(tmp_path):
    campaign_name = "preview-only-" + tmp_path.name
    destination = ROOT / "nn_meta" / "campaigns" / campaign_name
    result = subprocess.run(["bash", str(ROOT / "scripts" / "run_research_local.sh"),
                             "--campaign", campaign_name, "--pool", "v5", "--stage", "freeze",
                             "--symbols", "SPY", "--workers", "2"], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "PREVIEW" in result.stdout and "--merge" in result.stdout
    assert "freeze_shards/SPY.json" in result.stdout
    assert "build_meta_dataset" not in result.stdout
    assert not destination.exists()
    missing_stage = subprocess.run(["bash", str(ROOT / "scripts" / "run_research_local.sh"),
                                    "--campaign", campaign_name, "--pool", "v5"],
                                   capture_output=True, text=True)
    assert missing_stage.returncode != 0
    assert "--stage" in missing_stage.stderr


def test_candidate_preview_includes_raw_cache_selector(tmp_path):
    result = subprocess.run(["bash", str(ROOT / "scripts/run_research_local.sh"),
                             "--campaign", "candidate-preview", "--pool", "v6", "--stage", "freeze",
                             "--symbols", "SPY"], cwd=tmp_path, capture_output=True, text=True,
                            env=dict(os.environ, NN_META_DATA_CANDIDATE="repair-preview"))
    assert result.returncode == 0, result.stderr
    assert "NN_META_DATA_CANDIDATE=repair-preview" in result.stdout
    assert "data_candidates/repair-preview/cache" in result.stdout


def test_launcher_rejects_unsafe_scope_and_out_of_order_stages():
    for arguments in (["--campaign", "../old", "--pool", "v6", "--stage", "freeze"],
                      ["--campaign", "pilot", "--pool", "v3", "--stage", "freeze"],
                      ["--campaign", "pilot", "--pool", "v6", "--stage", "build", "--stage", "freeze"]):
        with pytest.raises(SystemExit):
            runner.parse_args(arguments)
    for symbols in ("../SPY", "SPY,,QQQ", "SPY,SPY", ""):
        with pytest.raises(runner.CampaignError):
            runner.selected_symbols(symbols, [])


def test_output_symlink_cannot_redirect_writes(campaign, tmp_path):
    campaign.ROOT.mkdir(parents=True, exist_ok=True)
    other = tmp_path / "historical"
    other.mkdir()
    (campaign.ROOT / "campaigns").symlink_to(other, target_is_directory=True)
    with pytest.raises(runner.CampaignError, match="symlink"):
        runner.safe_outputs(campaign)
    assert list(other.iterdir()) == []


def test_two_way_pinned_coverage_catches_underlying_hole(campaign):
    days = campaign.DATA_CACHE / "flatfiles_15m"
    days.mkdir(parents=True)
    for day in ("2025-03-28", "2025-03-31", "2025-04-01", "2025-04-02"):
        (days / f"{day}.parquet").touch()
    pd.DataFrame({"timestamp": pd.to_datetime(["2025-03-28", "2025-04-01"])}).to_parquet(
        campaign.DATA_CACHE / "underlying_15m.parquet")
    report = runner.coverage_gaps(campaign.DATA_CACHE, campaign.WINDOW_START, campaign.WINDOW_END)
    assert report["missing_underlying"] == ["2025-03-31"]
    assert report["missing_options"] == []
    assert report["option_days"] == 3  # out-of-window extra is irrelevant
    with pytest.raises(runner.CampaignError, match="coverage gaps"):
        runner.require_coverage(campaign)


def test_repaired_candidate_requires_raw_context_and_resolved_basis_gates(campaign, monkeypatch):
    campaign.DATA_CANDIDATE = "repair"
    monkeypatch.setattr(runner, "coverage_gaps", lambda *args: {
        "option_days": 3, "underlying_days": 3, "missing_options": [], "missing_underlying": []})
    path = campaign.DATA_CACHE / "repair_manifest.json"
    manifest = {"coverage_result": {"passed": True}, "context_status": "refreshed_raw_spot"}
    path.write_text(json.dumps(manifest))
    with pytest.raises(runner.CampaignError, match="option daily"):
        runner.require_coverage(campaign)
    manifest["options_daily_raw_filter_verified"] = True
    manifest["unresolved_model_gates"] = ["raw15m pending"]
    path.write_text(json.dumps(manifest))
    with pytest.raises(runner.CampaignError, match="price-basis"):
        runner.require_coverage(campaign)
    manifest["unresolved_model_gates"] = []
    path.write_text(json.dumps(manifest))
    assert runner.require_coverage(campaign)["option_days"] == 3


def test_candidate_seal_refuses_same_size_mutation_and_file_list_change(campaign):
    campaign.DATA_CANDIDATE = "repair"
    path = campaign.DATA_CACHE / "repair_manifest.json"
    expected = {"contracts.parquet": "verified-hash"}
    path.write_text(json.dumps({"sealed_cache_sha256": expected}))
    fingerprint = {"files": [{"path": "cache/contracts.parquet", "sha256": "verified-hash"},
                              {"path": "cache/repair_manifest.json", "sha256": "self-hash"}]}
    runner.validate_candidate_seal(campaign, fingerprint)
    fingerprint["files"][0]["sha256"] = "mutated-same-size-hash"
    with pytest.raises(runner.CampaignError, match="bytes or file list"):
        runner.validate_candidate_seal(campaign, fingerprint)
    fingerprint["files"][0]["sha256"] = "verified-hash"
    fingerprint["files"].append({"path": "cache/new-input.parquet", "sha256": "new"})
    with pytest.raises(runner.CampaignError, match="bytes or file list"):
        runner.validate_candidate_seal(campaign, fingerprint)


def test_coverage_failure_precedes_any_run_or_output(campaign, monkeypatch):
    monkeypatch.setattr(runner, "load_config", lambda args: campaign)
    monkeypatch.setattr(runner, "coverage_gaps", lambda *args: {
        "option_days": 3, "underlying_days": 2, "missing_options": [],
        "missing_underlying": ["2025-03-31"]})
    monkeypatch.setattr(runner, "run_plan", lambda *a: pytest.fail("must not launch"))
    assert runner.main(["--campaign", "pilot", "--pool", "v6", "--stage", "freeze", "--run"]) == 1
    assert not (campaign.ROOT / "campaigns").exists()


def test_freeze_uses_per_symbol_shards_and_merges_only_expected_paths(campaign, monkeypatch):
    from nn_meta.feature_contract import CONTRACT_VERSION
    symbols = ["QQQ", "SPY"]
    plan = runner.command_plan(campaign, symbols, ["freeze"], 3)
    shard_dir = campaign.ARTIFACTS / "freeze_shards"
    shard_dir.mkdir(parents=True)
    (shard_dir / "STALE.json").write_text("historical unrelated shard")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if "--symbols" in command:
            symbol = command[command.index("--symbols") + 1]
            output = Path(command[command.index("--out") + 1])
            output.write_text(json.dumps({"feature_contract_version": CONTRACT_VERSION,
                                           "symbols": {symbol: {}}, "skipped": []}))

    monkeypatch.setattr(runner, "run_command", fake_run)
    runner.run_plan(campaign, symbols, plan, 2, {})
    merged = next(command for command in calls if "--merge" in command)
    assert merged[merged.index("--merge") + 1].split(",") == [str(shard_dir / f"{s}.json") for s in symbols]
    assert "STALE" not in str(merged)
    calls.clear()
    runner.run_plan(campaign, symbols, plan, 1, {})  # same scope, different worker count
    assert sum("--symbols" in c for c in calls) == 2


def test_failed_worker_prevents_merge_and_following_stages(campaign, monkeypatch):
    calls = []

    def fail(command, **kwargs):
        calls.append(command)
        raise runner.CampaignError("worker failed")

    monkeypatch.setattr(runner, "run_command", fail)
    plan = runner.command_plan(campaign, ["SPY"], ["freeze", "build"], 3)
    with pytest.raises(runner.CampaignError, match="worker failed"):
        runner.run_plan(campaign, ["SPY"], plan, 1, {})
    assert len(calls) == 1 and "--merge" not in calls[0]


def test_successful_exit_with_wrong_shard_is_refused_before_merge(campaign, monkeypatch):
    from nn_meta.feature_contract import CONTRACT_VERSION
    calls = []

    def wrong_shard(command, **kwargs):
        calls.append(command)
        Path(command[command.index("--out") + 1]).write_text(json.dumps({
            "feature_contract_version": CONTRACT_VERSION, "symbols": {"WRONG": {}}, "skipped": []}))

    monkeypatch.setattr(runner, "run_command", wrong_shard)
    with pytest.raises(runner.CampaignError, match="exactly SPY"):
        runner.run_plan(campaign, ["SPY"], runner.command_plan(campaign, ["SPY"], ["freeze"], 3), 1, {})
    assert len(calls) == 1


def test_scope_change_refuses_mixing_pilot_and_full_campaign(campaign, monkeypatch):
    monkeypatch.setattr(runner, "run_command", lambda *a, **kw: None)
    runner.run_plan(campaign, ["SPY"], [], 1, {})
    with pytest.raises(runner.CampaignError, match="scope changed"):
        runner.run_plan(campaign, ["QQQ", "SPY"], [], 2, {})


def test_subprocess_failure_status_is_not_reported_as_success(tmp_path):
    with pytest.raises(runner.CampaignError, match="failed \\(7\\)"):
        runner.run_command([sys.executable, "-c", "raise SystemExit(7)"],
                           environment=dict(os.environ), cwd=tmp_path, log=tmp_path / "stage.log")


def test_freeze_merge_cli_honors_explicit_output(monkeypatch, tmp_path):
    from nn_meta import freeze_baseline
    seen = []
    monkeypatch.setattr(freeze_baseline.baseline, "merge_specs", lambda shards, out_path: seen.append((shards, out_path)))
    target = tmp_path / "new" / "baseline_spec.json"
    monkeypatch.setattr(sys, "argv", ["freeze_baseline", "--merge", "SPY.json,QQQ.json", "--out", str(target)])
    freeze_baseline.main()
    assert seen == [(["SPY.json", "QQQ.json"], str(target))]


@pytest.mark.parametrize("change", ["same-size-bytes", "added-input", "removed-input", "source", "pit"])
def test_resuming_campaign_refuses_changed_input_identity(campaign, change):
    source = campaign.ROOT.parent / "signals" / "example.py"
    source.parent.mkdir()
    source.write_text("VALUE = 1\n")
    pit = campaign.ROOT.parent / "v3" / "artifacts" / "universe_pit" / "2025-01.json"
    pit.parent.mkdir(parents=True)
    pit.write_text('{"members": ["SPY"]}\n')
    runner.run_plan(campaign, ["SPY"], [], 1, {})
    manifest = campaign.ROOT / "campaigns" / "pilot" / "v6" / "campaign_scope.json"
    before = manifest.read_bytes()
    original = campaign.DATA_CACHE / "contracts.parquet"
    if change == "same-size-bytes":
        old_stat = original.stat()
        original.write_bytes(b"raw-input-B")
        os.utime(original, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
    elif change == "added-input":
        (campaign.DATA_CACHE / "new.parquet").write_bytes(b"additional")
    elif change == "removed-input":
        original.unlink()
    elif change == "source":
        source.write_text("VALUE = 2\n")
    else:
        pit.write_text('{"members": ["QQQ"]}\n')
    with pytest.raises(runner.CampaignError, match="scope changed"):
        runner.run_plan(campaign, ["SPY"], [], 1, {})
    assert manifest.read_bytes() == before


def test_credentials_and_temporary_files_are_never_fingerprinted(campaign, monkeypatch):
    excluded = [".env", ".env.production", "credentials.json", "api_token.txt",
                "private.key", "bars.parquet.tmp", "writer.lock"]
    for filename in excluded:
        (campaign.DATA_CACHE / filename).write_text("must-not-read")
    real_hash = runner._sha256

    def guarded_hash(path):
        assert path.name not in excluded
        return real_hash(path)

    monkeypatch.setattr(runner, "_sha256", guarded_hash)
    before = runner.input_fingerprint(campaign)
    for filename in excluded:
        (campaign.DATA_CACHE / filename).write_text("changed-sensitive-or-transient")
    assert runner.input_fingerprint(campaign) == before
    assert "must-not-read" not in json.dumps(before)


def test_changed_raw_inputs_between_stages_prevent_next_stage(campaign, monkeypatch):
    calls = []

    def mutate_input(command, **kwargs):
        calls.append(command)
        (campaign.DATA_CACHE / "contracts.parquet").write_bytes(b"raw-input-B")

    monkeypatch.setattr(runner, "run_command", mutate_input)
    plan = runner.command_plan(campaign, ["SPY"], ["build", "assemble"], 3)
    with pytest.raises(runner.CampaignError, match="changed during build"):
        runner.run_plan(campaign, ["SPY"], plan, 1, {})
    assert len(calls) == 1


@pytest.mark.parametrize("stage", ["assemble", "evaluate", "finalize"])
def test_final_stage_input_mutation_cannot_report_success(campaign, monkeypatch, capsys, stage):
    def mutate_input(*args, **kwargs):
        (campaign.DATA_CACHE / "contracts.parquet").write_bytes(b"raw-input-B")

    monkeypatch.setattr(runner, "run_command", mutate_input)
    with pytest.raises(runner.CampaignError, match=f"changed during {stage}"):
        runner.run_plan(campaign, ["SPY"], runner.command_plan(campaign, ["SPY"], [stage], 3), 1, {})
    assert f"Completed {stage}" not in capsys.readouterr().out
