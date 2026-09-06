"""Recompare an explicitly reviewed pack of actual external TV captures.

This validates declared raw-field coverage and source-default settings. User
capture/reviewer/precomputed-producer attestations are not authenticated origin,
exhaustive branch coverage, normalized-feature parity or permission to ship.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re

import pandas as pd

from indicators.tradingview_registry import build_catalog
from nn_meta import tradingview_features as projection
from nn_meta import tradingview_proposals as proposals
from scripts import tradingview_fixture as fixture

SUCCESS = {"matched", "matched_unavailable", "matched_with_unavailable"}
REF_KEYS = {"csv", "metadata", "local_csv", "local_metadata", "instrumentation_manifest", "instrumented_source"}
SNAPSHOT_SOURCES = {"I8HrQVRv", "Tm1cGCPD"}


class ParityPackError(ValueError):
    """Missing, stale, mismatched or insufficient declared external evidence."""


def _require(condition, message):
    if not condition:
        raise ParityPackError(message)


def _review(value, *, fields=False):
    keys = {"reviewer", "reviewed_at", "notes", "feature_scope_verified"}
    if fields:
        keys |= {"feature_fields", "source_defaults_verified"}
    _require(isinstance(value, dict) and set(value) == keys, "explicit parity review fields are required")
    _require(all(isinstance(value[k], str) and value[k].strip() for k in ("reviewer", "reviewed_at", "notes")),
             "reviewer, timestamp and review notes are required")
    stamp = pd.Timestamp(value["reviewed_at"])
    _require(not pd.isna(stamp) and stamp.tzinfo is not None, "review timestamp must include UTC offset")
    _require(value["feature_scope_verified"] is True, "feature-field scope must be explicitly reviewed")
    if fields:
        names = value["feature_fields"]
        _require(isinstance(names, list) and bool(names) and all(isinstance(x, str) and x for x in names)
                 and len(names) == len(set(names)), "review must name distinct covered source fields")
        _require(value["source_defaults_verified"] is True, "source defaults must be verified against the captured chart")


def _ref(value, parent, tracked):
    _require(isinstance(value, dict) and set(value) == {"path", "sha256"}, "each capture reference requires path and sha256")
    _require(isinstance(value["path"], str) and bool(value["path"].strip()), "capture reference path is missing")
    _require(isinstance(value["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]),
             "capture reference requires a lowercase SHA256")
    path = Path(value["path"])
    if not path.is_absolute():
        path = parent / path
    _require(not path.is_symlink() and not any(part.is_symlink() for part in path.parents),
             f"symlinked external evidence path is not immutable: {path}")
    path = path.resolve()
    _require(path.is_file(), f"missing external capture file: {path}; retain the actual CSV and sidecars")
    digest = fixture.file_sha256(path)
    _require(digest == value["sha256"], f"external capture hash mismatch: {path}")
    _require(path not in tracked or tracked[path] == digest, "conflicting hashes for the same evidence path")
    tracked[path] = digest
    return path


def _required(schema, proposal_events=None):
    required = {script: {} for script in schema["sources"].values()}
    for spec in schema["columns"]:
        if (spec["source"], spec["field"]) == ("setup", "session_gap"):
            continue  # Python adapter diagnostics have no upstream Pine signal.
        script = schema["sources"][spec["source"]]
        required[script][spec["field"]] = "event" if spec["transform"] == "event" else "numeric"
        if spec["valid_when"]:
            required[script][spec["valid_when"]] = "event"
    for script, events in (proposal_events or {}).items():
        _require(script in required, "proposal events name a source outside the thirteen-feature contract")
        required[script].update({event: "event" for event in events})
    return required


def _proposal_scope(contract, catalog):
    registry = proposals.registry_metadata(minimum_tick=contract["minimum_tick"],
        session_policy=contract["session_policy"], vwap_mode=contract["vwap_mode"])
    events = registry["required_source_event_fields"]
    source_ids = {r["script_id"] for r in registry["sources"].values()}
    _require(len(registry["strategies"]) == 8 and len(source_ids) == 8 and set(events) == source_ids,
             "proposal registry must declare exactly eight source event contracts")
    _require(all(isinstance(v, (list, tuple)) and bool(v) and len(v) == len(set(v))
                 and all(isinstance(name, str) and name for name in v) for v in events.values()),
             "proposal registry has invalid required event fields")
    registry_hash = fixture.hash_json(registry)
    runtime_hash = fixture.file_sha256(proposals.__file__)
    scope = {"registry_sha256": registry_hash, "runtime_sha256": runtime_hash,
             "required_source_event_fields": events,
             "source_fixture_identities": {s: catalog[s]["fixture_identity_sha256"] for s in sorted(source_ids)}}
    return {"registry_sha256": registry_hash, "runtime_sha256": runtime_hash,
            "source_scope_sha256": fixture.hash_json(scope)}, events, registry


def verify_parity_pack(path, expected_sha256):
    """Hash-anchor and recompare all files; return scoped attested verification.

    Pack schema: feature_contract(minimum_tick,session_policy,vwap_mode,
    feature_schema_sha256), proposal_contract(registry_sha256,runtime_sha256,
    source_scope_sha256), review, and fixtures[]. Each fixture names script_id,
    files{csv,metadata[,local_csv,local_metadata,instrumentation_manifest,
    instrumented_source]} as {path,sha256}, and review with feature_fields and
    source_defaults_verified. No pre-existing comparison report is an input.

    Settings in metadata must exactly match feature_schema's parameter object;
    runtime context placeholders remain in that declaration and must be supplied
    by the retained local producer/context evidence. This function does not run
    the other ten Python adapters from those context streams.

    Every required numeric field needs a finite comparison in at least one
    capture. Additional unavailable-state snapshots remain narrow missingness
    evidence; they cannot authorize later active use. Symlinked evidence files
    or parent directories are rejected before path resolution.
    """
    tracked = {}
    try:
        pack_path = _ref({"path": str(path), "sha256": expected_sha256}, Path.cwd(), tracked)
        pack = fixture.load_metadata(pack_path)
        _require(isinstance(pack, dict) and set(pack) == {"schema_version", "feature_contract", "proposal_contract", "review", "fixtures"}
                 and pack["schema_version"] == 1, "unsupported parity pack; provide explicit capture references, not reports")
        _review(pack["review"])
        contract = pack["feature_contract"]
        _require(isinstance(contract, dict) and set(contract) ==
                 {"minimum_tick", "session_policy", "vwap_mode", "feature_schema_sha256"},
                 "parity pack must declare minimum tick, session policy, VWAP mode and feature schema hash")
        runtime_paths = [Path(__file__).resolve(), Path(projection.__file__).resolve(), Path(fixture.__file__).resolve(),
                         Path(proposals.__file__).resolve()]
        runtime = {str(p): fixture.file_sha256(p) for p in runtime_paths}
        schema = projection.feature_schema(minimum_tick=contract["minimum_tick"],
            session_policy=contract["session_policy"], vwap_mode=contract["vwap_mode"])
        _require(fixture.hash_json(schema) == contract["feature_schema_sha256"], "stale source-default feature schema; review current settings")
        catalog = {row["script_id"]: row for row in build_catalog()["scripts"]}
        proposal_contract, proposal_events, proposal_registry = _proposal_scope(contract, catalog)
        _require(pack["proposal_contract"] == proposal_contract,
                 "stale proposal registry/default grid/runtime or source event scope; review current eight-proposal contract")
        required = _required(schema, proposal_events)
        _require(len(required) == 13 and set(required) == set(catalog), "current feature contract does not name all thirteen pinned sources")
        aliases = {script: alias for alias, script in schema["sources"].items()}
        covered = {script: set() for script in required}
        finite_or_event = {script: set() for script in required}
        evidence = []
        records = pack["fixtures"]
        _require(isinstance(records, list) and bool(records), "parity pack contains no actual capture files")
        for index, record in enumerate(records):
            _require(isinstance(record, dict) and set(record) == {"script_id", "files", "review"},
                     f"fixture {index}: explicit file references and review required; reports cannot substitute")
            script = record["script_id"]
            _require(script in required, f"fixture {index}: unknown selected source {script!r}")
            _review(record["review"], fields=True)
            files = record["files"]
            _require(isinstance(files, dict) and {"csv", "metadata"} <= set(files) <= REF_KEYS,
                     f"{script}: raw CSV and capture metadata references are required")
            for left, right in (("local_csv", "local_metadata"), ("instrumentation_manifest", "instrumented_source")):
                _require((left in files) == (right in files), f"{script}: {left} and {right} must be paired")
            paths = {key: _ref(ref, pack_path.parent, tracked) for key, ref in files.items()}
            names = list(paths.values())
            _require(not any(left.samefile(right) for i, left in enumerate(names) for right in names[i + 1:]),
                     f"{script}: distinct evidence roles cannot alias one file")
            metadata = fixture.load_metadata(paths["metadata"])
            _require(metadata.get("script_id") == script, f"{script}: metadata names another publication")
            _require(metadata.get("fixture_identity_sha256") == catalog[script]["fixture_identity_sha256"],
                     f"{script}: stale Python/source fixture identity")
            _require(fixture.hash_json(metadata.get("parameters")) == fixture.hash_json(schema["parameters"][aliases[script]]),
                     f"{script}: captured parameters differ from source-default feature settings")
            capture = metadata.get("capture", {})
            _require(capture.get("timeframe") == "15m" and capture.get("minimum_tick") == contract["minimum_tick"],
                     f"{script}: capture timeframe/minimum tick differs from feature scope")
            if script in SNAPSHOT_SOURCES:
                _require(metadata.get("comparison_scope", {}).get("kind") == "terminal_snapshot",
                         f"{script}: last-bar profile fields require explicit terminal snapshots and execution sequence")
            kwargs = {}
            if "local_csv" in paths:
                kwargs.update(local_csv=paths["local_csv"], local_metadata=fixture.load_metadata(paths["local_metadata"]))
            if "instrumentation_manifest" in paths:
                kwargs.update(instrumented_source=paths["instrumented_source"],
                              instrumentation_manifest=fixture.load_metadata(paths["instrumentation_manifest"]))
            report = fixture.compare_fixture(paths["csv"], metadata, **kwargs)
            _require(report.get("status") in SUCCESS, f"{script}: actual external comparison mismatched; inspect retained capture outputs")
            _require(report.get("active_pool_admission") is False and report.get("origin_authenticated") is False,
                     f"{script}: comparison must remain scoped, with unauthenticated origin")
            _require(report.get("fixture_identity_sha256") == catalog[script]["fixture_identity_sha256"],
                     f"{script}: comparison runtime identity differs")
            columns = {row["python_column"]: row for row in report["comparison"]}
            declared = set(record["review"]["feature_fields"])
            _require(declared <= set(required[script]), f"{script}: review contains a field outside selected source scope")
            _require(declared <= set(columns), f"{script}: reviewed field lacks an actual mapped comparison")
            for field in declared:
                result = columns[field]
                _require(result.get("matched") is True and result.get("status") in ("matched", "matched_unavailable"),
                         f"{script}.{field}: missing successful field evidence")
                _require(result.get("kind") == required[script][field], f"{script}.{field}: numerical/event semantics differ from feature schema")
                if result["status"] == "matched_unavailable":
                    _require(result.get("expectation") == "unavailable" and result.get("evidence_kind") == "missingness_only"
                             and result.get("finite_pair_count") == 0, f"{script}.{field}: unavailable evidence was relabeled")
                else:
                    _require(result["kind"] == "event" or result.get("finite_pair_count", 0) > 0,
                             f"{script}.{field}: numerical evidence contains no finite pairs")
                    finite_or_event[script].add(field)
                covered[script].add(field)
            evidence.append({"script_id": script, "file_references": deepcopy(files), "review": deepcopy(record["review"]),
                             "comparison_report": report})
        missing = {script: sorted(set(fields) - covered[script]) for script, fields in required.items() if set(fields) - covered[script]}
        _require(not missing, f"missing reviewed actual TradingView field evidence: {missing}")
        unavailable = {s: sorted(covered[s] - finite_or_event[s]) for s in covered if covered[s] - finite_or_event[s]}
        _require(not unavailable,
                 f"missing finite numerical/event evidence for required fields: {unavailable}; "
                 "missingness-only snapshots cannot cover later active historical use. Capture active states "
                 "(including extended-session ICT ranges where needed); retain unavailable observations separately.")
        _require(all(not p.is_symlink() and not any(parent.is_symlink() for parent in p.parents)
                     and fixture.file_sha256(p) == digest for p, digest in tracked.items()),
                 "parity pack/capture evidence changed during verification")
        _require(all(fixture.file_sha256(p) == digest for p, digest in runtime.items()), "parity verifier/feature/fixture runtime changed during verification")
        current = {r["script_id"]: r["fixture_identity_sha256"] for r in build_catalog()["scripts"]}
        _require(current == {s: r["fixture_identity_sha256"] for s, r in catalog.items()}, "source runtime changed across capture comparisons")
        _require(fixture.hash_json(projection.feature_schema(minimum_tick=contract["minimum_tick"],
            session_policy=contract["session_policy"], vwap_mode=contract["vwap_mode"])) == contract["feature_schema_sha256"],
            "source-default feature settings changed during verification")
        _require(_proposal_scope(contract, {r["script_id"]: r for r in build_catalog()["scripts"]})[0] == proposal_contract,
                 "proposal registry/default grid/event scope changed during verification")
        return {"schema_version": 1, "status": "verified_scoped_captures", "pack_sha256": expected_sha256,
                "feature_contract": contract, "feature_schema": schema, "source_count": len(covered),
                "proposal_contract": proposal_contract, "proposal_registry": proposal_registry,
                "source_proposal_scope_sha256": proposal_contract["source_scope_sha256"],
                "required_proposal_source_events": deepcopy(proposal_events),
                "covered_fields": {s: sorted(v) for s, v in covered.items()}, "unavailable_only_fields": unavailable,
                "review": pack["review"], "evidence": evidence, "verification_runtime_sha256": runtime,
                "input_files": {str(p): digest for p, digest in tracked.items()},
                "origin_authenticated": False, "model_admission": False,
                "scope_note": "Attested captured raw fields/default settings only. Missingness is not finite parity; capture/review/local producer origin is unauthenticated. No exhaustive branch, external context, normalization or shipping approval is implied."}
    except ParityPackError:
        raise
    except (ValueError, TypeError, KeyError, OSError, AttributeError) as error:
        raise ParityPackError(f"invalid parity pack or external capture: {error}") from error
