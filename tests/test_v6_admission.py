"""Pack-boundary tests using a stub comparator; never external parity evidence.

Real comparator/source/CSV/snapshot semantics are exercised separately in the
108 fixture tests. These tests exercise the aggregate all-thirteen evidence gate.
"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from nn_meta import v6_admission as admission


@pytest.fixture
def pack(tmp_path, monkeypatch):
    f = admission.fixture
    schema = admission.projection.feature_schema(minimum_tick=.01, session_policy="source_literal", vwap_mode="observed")
    catalog = {r["script_id"]: r for r in admission.build_catalog()["scripts"]}
    feature_contract = {"minimum_tick": .01, "session_policy": "source_literal", "vwap_mode": "observed",
                        "feature_schema_sha256": f.hash_json(schema)}
    proposal_contract, events, _ = admission._proposal_scope(feature_contract, catalog)
    required = admission._required(schema, events)
    aliases = {v: k for k, v in schema["sources"].items()}
    review = {"reviewer": "SYNTHETIC UNIT TEST", "reviewed_at": "2026-09-06T00:00:00Z",
              "notes": "Stub comparator wiring only, no capture evidence", "feature_scope_verified": True}
    records = []
    for script, fields in required.items():
        csv = tmp_path / f"{script}.csv"
        csv.write_text("synthetic placeholder,not actual chart data\n")
        metadata = tmp_path / f"{script}.json"
        metadata.write_text(json.dumps({"script_id": script, "fixture_identity_sha256": catalog[script]["fixture_identity_sha256"],
            "parameters": schema["parameters"][aliases[script]], "capture": {"timeframe": "15m", "minimum_tick": .01},
            "comparison_scope": {"kind": "terminal_snapshot" if script in admission.SNAPSHOT_SOURCES else "full_series"},
            "columns": [{"python_column": field, "kind": kind} for field, kind in fields.items()]}))
        records.append({"script_id": script, "files": {
            "csv": {"path": csv.name, "sha256": f.file_sha256(csv)},
            "metadata": {"path": metadata.name, "sha256": f.file_sha256(metadata)}},
            "review": {**review, "feature_fields": sorted(fields), "source_defaults_verified": True}})
    body = {"schema_version": 1, "review": review, "feature_contract": feature_contract,
            "proposal_contract": proposal_contract, "fixtures": records}
    path = tmp_path / "pack.json"
    calls = []
    def comparator(csv, metadata, **kwargs):
        calls.append((csv, deepcopy(metadata), kwargs))
        rows = []
        for column in metadata["columns"]:
            unavailable = column.get("expectation") == "unavailable"
            rows.append({**column, "matched": True, "status": "matched_unavailable" if unavailable else "matched",
                         "evidence_kind": "missingness_only" if unavailable else "numerical",
                         "finite_pair_count": 0 if unavailable else 1})
        return {"status": "matched_with_unavailable" if any(r["status"] == "matched_unavailable" for r in rows) else "matched",
                "fixture_identity_sha256": metadata["fixture_identity_sha256"], "comparison": rows,
                "active_pool_admission": False, "origin_authenticated": False}
    monkeypatch.setattr(f, "compare_fixture", comparator)
    def write():
        path.write_text(json.dumps(body, indent=2) + "\n")
        return path, f.file_sha256(path)
    def change_metadata(record, change):
        ref = record["files"]["metadata"]
        target = tmp_path / ref["path"]
        value = json.loads(target.read_text())
        change(value)
        target.write_text(json.dumps(value))
        ref["sha256"] = f.file_sha256(target)
    return body, write, change_metadata, calls


def test_all_thirteen_recompared_with_field_scope_and_input_hashes(pack):
    body, write, _, calls = pack
    path, digest = write()
    result = admission.verify_parity_pack(path, digest)
    assert result["status"] == "verified_scoped_captures" and result["source_count"] == 13
    assert len(calls) == 13 and len(result["input_files"]) == 27
    assert result["input_files"][str(path.resolve())] == digest
    assert not result["origin_authenticated"] and not result["model_admission"]
    assert "session_gap" not in result["covered_fields"]["XWuYNmhD"]
    assert "profile_ready" in result["covered_fields"]["I8HrQVRv"]
    assert "chart_poc_fresh" in result["covered_fields"]["Tm1cGCPD"]
    assert result["unavailable_only_fields"] == {}
    assert result["source_proposal_scope_sha256"] == body["proposal_contract"]["source_scope_sha256"]
    assert "VWAP_long_exit" in result["covered_fields"]["XWuYNmhD"]
    assert "short_exit" in result["covered_fields"]["c25U5rsF"]


def test_missing_source_or_required_validity_field_fails(pack):
    body, write, change, _ = pack
    removed = body["fixtures"].pop()
    with pytest.raises(admission.ParityPackError, match="missing reviewed actual"):
        admission.verify_parity_pack(*write())
    body["fixtures"].append(removed)
    record = next(r for r in body["fixtures"] if r["script_id"] == "Tm1cGCPD")
    record["review"]["feature_fields"].remove("chart_poc_fresh")
    with pytest.raises(admission.ParityPackError, match="chart_poc_fresh"):
        admission.verify_parity_pack(*write())


@pytest.mark.parametrize("mutation", [
    lambda b: b["review"].update(feature_scope_verified=False),
    lambda b: b["review"].update(notes=""),
    lambda b: b["review"].update(reviewed_at="2026-09-06"),
    lambda b: b["fixtures"][0]["review"].update(source_defaults_verified=False),
    lambda b: b["fixtures"][0]["review"].update(feature_fields=["invented_signal"]),
    lambda b: b["feature_contract"].update(feature_schema_sha256="stale"),
    lambda b: b["proposal_contract"].update(registry_sha256="stale"),
    lambda b: b["proposal_contract"].update(runtime_sha256="stale"),
    lambda b: b["proposal_contract"].update(source_scope_sha256="stale"),
    lambda b: b.update(active_pool_admission=True),
    lambda b: b["fixtures"][0].update(report={"status": "matched"}),
])
def test_unreviewed_stale_or_report_only_packs_fail(pack, mutation):
    body, write, _, _ = pack
    mutation(body)
    with pytest.raises(admission.ParityPackError):
        admission.verify_parity_pack(*write())


@pytest.mark.parametrize("mutation", [
    lambda m: m["parameters"].update(length=99),
    lambda m: m["capture"].update(minimum_tick=.1),
    lambda m: m["capture"].update(timeframe="1h"),
    lambda m: m.update(script_id="wrong"),
    lambda m: m.update(fixture_identity_sha256="stale"),
    lambda m: m["columns"][0].update(kind="event"),
    lambda m: m.update(columns=[]),
])
def test_actual_captured_parameters_and_mapped_fields_checked(pack, mutation):
    body, write, change, _ = pack
    change(body["fixtures"][0], mutation)
    with pytest.raises(admission.ParityPackError):
        admission.verify_parity_pack(*write())


@pytest.mark.parametrize("script", sorted(admission.SNAPSHOT_SOURCES))
def test_last_bar_profiles_require_terminal_capture_scope(pack, script):
    body, write, change, _ = pack
    record = next(r for r in body["fixtures"] if r["script_id"] == script)
    change(record, lambda m: m.update(comparison_scope={"kind": "full_series"}))
    with pytest.raises(admission.ParityPackError, match="terminal snapshots"):
        admission.verify_parity_pack(*write())


def test_unavailable_only_cannot_cover_later_active_feature_use(pack):
    body, write, change, _ = pack
    record = body["fixtures"][0]
    def missing(m):
        next(c for c in m["columns"] if c["kind"] == "numeric")["expectation"] = "unavailable"
    change(record, missing)
    with pytest.raises(admission.ParityPackError, match="missing finite numerical/event evidence"):
        admission.verify_parity_pack(*write())


def test_unavailable_observation_retained_when_separate_finite_capture_covers_field(pack):
    body, write, change, _ = pack
    record = deepcopy(body["fixtures"][0])
    path, _ = write()
    source = path.parent / record["files"]["metadata"]["path"]
    target = source.with_name("additional-missingness.json")
    target.write_bytes(source.read_bytes())
    record["files"]["metadata"] = {"path": target.name, "sha256": admission.fixture.file_sha256(target)}
    def missing(m):
        next(c for c in m["columns"] if c["kind"] == "numeric")["expectation"] = "unavailable"
    change(record, missing)
    body["fixtures"].append(record)
    result = admission.verify_parity_pack(*write())
    assert result["unavailable_only_fields"] == {}
    assert len(result["evidence"]) == 14
    assert any(c.get("status") == "matched_unavailable" for c in result["evidence"][-1]["comparison_report"]["comparison"])


def test_mismatched_comparator_report_cannot_be_overridden(pack, monkeypatch):
    _, write, _, _ = pack
    monkeypatch.setattr(admission.fixture, "compare_fixture", lambda *a, **k: {"status": "mismatch"})
    with pytest.raises(admission.ParityPackError, match="actual external comparison mismatched"):
        admission.verify_parity_pack(*write())


def test_pack_anchor_and_raw_file_tamper_fail(pack):
    body, write, _, _ = pack
    path, digest = write()
    with pytest.raises(admission.ParityPackError, match="hash mismatch"):
        admission.verify_parity_pack(path, "0" * 64)
    csv = path.parent / body["fixtures"][0]["files"]["csv"]["path"]
    csv.write_text("mutated raw evidence")
    with pytest.raises(admission.ParityPackError, match="hash mismatch"):
        admission.verify_parity_pack(path, digest)


def test_comparison_time_evidence_mutation_caught(pack, monkeypatch):
    _, write, _, _ = pack
    path, digest = write()
    original = admission.fixture.compare_fixture
    changed = False
    def mutate(csv, metadata, **kwargs):
        nonlocal changed
        result = original(csv, metadata, **kwargs)
        if not changed:
            changed = True
            Path(csv).write_text("changed after comparator read")
        return result
    monkeypatch.setattr(admission.fixture, "compare_fixture", mutate)
    with pytest.raises(admission.ParityPackError, match="changed during verification"):
        admission.verify_parity_pack(path, digest)


def test_late_symlink_with_identical_bytes_is_rejected(pack, monkeypatch):
    _, write, _, _ = pack
    path, digest = write()
    original = admission.fixture.compare_fixture
    changed = False
    def swap(csv, metadata, **kwargs):
        nonlocal changed
        result = original(csv, metadata, **kwargs)
        if not changed:
            changed = True
            csv = Path(csv)
            copied = csv.with_name("same-bytes.csv")
            copied.write_bytes(csv.read_bytes())
            csv.unlink()
            csv.symlink_to(copied)
        return result
    monkeypatch.setattr(admission.fixture, "compare_fixture", swap)
    with pytest.raises(admission.ParityPackError, match="changed during verification"):
        admission.verify_parity_pack(path, digest)


def test_missing_pair_and_evidence_roles_alias_rejected(pack):
    body, write, _, _ = pack
    refs = body["fixtures"][0]["files"]
    refs["local_csv"] = deepcopy(refs["csv"])
    with pytest.raises(admission.ParityPackError, match="must be paired"):
        admission.verify_parity_pack(*write())
    refs["local_metadata"] = deepcopy(refs["metadata"])
    with pytest.raises(admission.ParityPackError, match="cannot alias"):
        admission.verify_parity_pack(*write())


@pytest.mark.parametrize("kind", ["file", "parent", "pack"])
def test_evidence_symlinks_rejected_before_resolve(pack, kind):
    body, write, _, _ = pack
    path, digest = write()
    if kind == "pack":
        alias = path.with_name("pack-link.json")
        alias.symlink_to(path)
        with pytest.raises(admission.ParityPackError, match="symlinked"):
            admission.verify_parity_pack(alias, digest)
    else:
        ref = body["fixtures"][0]["files"]["csv"]
        real = path.parent / ref["path"]
        alias = path.parent / "alias"
        alias.symlink_to(real if kind == "file" else path.parent, target_is_directory=kind == "parent")
        ref["path"] = str(alias if kind == "file" else alias / real.name)
        with pytest.raises(admission.ParityPackError, match="symlinked"):
            admission.verify_parity_pack(*write())


@pytest.mark.parametrize("script,field", [("XWuYNmhD", "VWAP_long_exit"), ("c25U5rsF", "short_entry"),
                                        ("hkKioUnL", "long_exit"), ("U7CZ8jtj", "bull_flip")])
def test_proposal_accepted_entries_and_exits_cannot_be_covered_by_raw_feature_flags(pack, script, field):
    body, write, _, _ = pack
    record = next(r for r in body["fixtures"] if r["script_id"] == script)
    record["review"]["feature_fields"].remove(field)
    with pytest.raises(admission.ParityPackError, match=field):
        admission.verify_parity_pack(*write())
