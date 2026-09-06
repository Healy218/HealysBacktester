"""Intake CLI tests; stub comparisons are not TradingView evidence."""
import json

import pytest

from scripts import prepare_v6_parity_pack as cli
from tests.test_v6_admission import pack  # shared synthetic comparator fixture


def test_template_tracks_full_runtime_contract_and_never_supplies_review():
    draft, checklist = cli.capture_template(minimum_tick=.01)
    assert checklist["source_count"] == 13
    assert checklist["field_count"] == 127
    assert checklist["proposal_event_count"] == 44
    assert not draft["review"]["feature_scope_verified"]
    assert not checklist["external_parity"] and not checklist["model_admission"]
    for record in draft["fixtures"]:
        assert not record["review"]["source_defaults_verified"]
        assert record["review"]["reviewer"] == ""
        assert all(ref["sha256"] == "" for ref in record["files"].values())
    snapshots = {r["script_id"] for r in checklist["sources"] if r["comparison_scope"] == "terminal_snapshot"}
    assert snapshots == cli.admission.SNAPSHOT_SOURCES


@pytest.mark.parametrize("tick", [0, -1, float("nan"), float("inf"), True])
def test_invalid_tick_cannot_create_template(tick):
    with pytest.raises(ValueError):
        cli.capture_template(minimum_tick=tick)


def test_prepare_preview_and_draft_refusal(tmp_path, capsys):
    output = tmp_path / "draft"
    args = ["prepare", "--minimum-tick", ".01", "--output", str(output)]
    assert cli.main(args) == 0
    assert not output.exists()
    assert cli.main([*args, "--run"]) == 0
    path = output / "pack.DRAFT.json"
    assert path.is_file()
    verification = tmp_path / "verification"
    assert cli.main(["verify", "--pack", str(path), "--expected-sha256", cli.sha256(path),
                     "--output", str(verification), "--run"]) == 1
    assert not verification.exists()
    assert "reviewer" in capsys.readouterr().err
    assert cli.main([*args, "--run"]) == 1  # never overwrite the draft


def test_verify_recompares_and_writes_anchored_report(pack, tmp_path):
    _, write, _, calls = pack
    path, digest = write()
    output = tmp_path / "verified"
    args = ["verify", "--pack", str(path), "--expected-sha256", digest, "--output", str(output)]
    assert cli.main(args) == 0
    assert len(calls) == 13 and not output.exists()
    assert cli.main([*args, "--run"]) == 0
    assert len(calls) == 26
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["report_sha256"] == cli.sha256(output / "verification.json")
    assert manifest["pack"]["sha256"] == digest
    assert manifest["complete"] and not manifest["freeze_started"]
    assert not manifest["model_admission"]


def test_stale_pack_hash_leaves_no_report(pack, tmp_path):
    _, write, _, calls = pack
    path, _ = write()
    output = tmp_path / "refused"
    assert cli.main(["verify", "--pack", str(path), "--expected-sha256", "0" * 64,
                     "--output", str(output), "--run"]) == 1
    assert not output.exists() and not calls


def test_symlinked_output_parent_refused(tmp_path):
    link = tmp_path / "alias"
    link.symlink_to(tmp_path, target_is_directory=True)
    assert cli.main(["prepare", "--minimum-tick", ".01", "--output", str(link / "draft"), "--run"]) == 1
    assert not (tmp_path / "draft").exists()


def test_evidence_mutation_during_report_write_has_no_completion_marker(pack, tmp_path, monkeypatch):
    _, write, _, _ = pack
    path, digest = write()
    original = cli._write
    def mutate(target, value):
        original(target, value)
        if target.name == "verification.json":
            path.write_text("{}")
    monkeypatch.setattr(cli, "_write", mutate)
    output = tmp_path / "incomplete"
    assert cli.main(["verify", "--pack", str(path), "--expected-sha256", digest,
                     "--output", str(output), "--run"]) == 1
    assert not (output / "manifest.json").exists()
