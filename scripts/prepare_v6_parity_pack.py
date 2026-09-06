"""Prepare unreviewed capture instructions or reverify actual v6 parity evidence.

No chart data, compilation attestations, or review approvals are generated.
The verifier always recomputes comparisons from hash-bound retained inputs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from nn_meta import v6_admission as admission
from nn_meta.v6_expansion import sha256


def capture_template(*, minimum_tick, session_policy="source_literal", vwap_mode="observed"):
    schema = admission.projection.feature_schema(minimum_tick=minimum_tick,
        session_policy=session_policy, vwap_mode=vwap_mode)
    catalog = {r["script_id"]: r for r in admission.build_catalog()["scripts"]}
    contract = {"minimum_tick": minimum_tick, "session_policy": session_policy,
                "vwap_mode": vwap_mode, "feature_schema_sha256": admission.fixture.hash_json(schema)}
    proposal_contract, events, _ = admission._proposal_scope(contract, catalog)
    required = admission._required(schema, events)
    aliases = {script: alias for alias, script in schema["sources"].items()}
    review = {"reviewer": "", "reviewed_at": "", "notes": "", "feature_scope_verified": False}
    records, checklist = [], []
    for script, fields in sorted(required.items()):
        records.append({"script_id": script, "files": {
            role: {"path": f"captures/{script}.{extension}", "sha256": ""}
            for role, extension in (("csv", "csv"), ("metadata", "json"))},
            "review": {**review, "feature_fields": sorted(fields), "source_defaults_verified": False}})
        checklist.append({"script_id": script, "feature_group": aliases[script],
            "fixture_identity_sha256": catalog[script]["fixture_identity_sha256"],
            "parameters": schema["parameters"][aliases[script]],
            "comparison_scope": "terminal_snapshot" if script in admission.SNAPSHOT_SOURCES else "full_series",
            "required_fields": fields, "required_proposal_events": events.get(script, [])})
    pack = {"schema_version": 1, "feature_contract": contract,
            "proposal_contract": proposal_contract, "review": review, "fixtures": records}
    instructions = {"schema": "v6-capture-checklist-v1", "status": "unreviewed_template",
        "source_count": len(required), "field_count": sum(map(len, required.values())),
        "proposal_event_count": sum(map(len, events.values())), "sources": checklist,
        "external_parity": False, "model_admission": False,
        "instructions": [
            "Retain actual chart CSVs and capture metadata; paths are relative to the pack.",
            "Use exact declared defaults, 15-minute bars, complete history and observed context.",
            "Add separate fixture records for additional sessions, active states or replay terminals.",
            "Every required numeric field needs finite evidence; missingness alone is insufficient.",
            "Retain paired local_csv/local_metadata for adapters requiring a local producer.",
            "Retain paired instrumentation_manifest/instrumented_source for edited chart sources.",
            "Only record review and TradingView compilation after they actually occur.",
            "Replace blank reference hashes with SHA256 of each retained file; separately record the final pack SHA256.",
            "Run verify with the separate pack hash. A passing pack does not verify full symbol context or tick coverage."]}
    return pack, instructions


def _fresh_directory(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("output cannot contain symlinks")
    if path.exists():
        raise ValueError("output must be a fresh directory; preserve prior evidence")
    return path


def _write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def prepare(args):
    output = _fresh_directory(args.output)
    pack, checklist = capture_template(minimum_tick=args.minimum_tick,
        session_policy=args.session_policy, vwap_mode=args.vwap_mode)
    if args.run:
        output.mkdir(parents=True, exist_ok=False)
        _write(output / "pack.DRAFT.json", pack)
        _write(output / "capture_checklist.json", checklist)
    return {"operation": "prepare", "written": args.run, "output": str(output), **checklist}


def verify(args):
    output = _fresh_directory(args.output)
    # Validate before creating output, so an ordinary refusal leaves no report.
    report = admission.verify_parity_pack(args.pack, args.expected_sha256)
    if args.run:
        output.mkdir(parents=True, exist_ok=False)
        _write(output / "verification.json", report)
        for path, digest in {**report["input_files"], **report["verification_runtime_sha256"]}.items():
            if sha256(path) != digest:
                raise ValueError("parity evidence/runtime changed before report completion")
        # Completion marker is last and explicitly does not claim freeze readiness.
        _write(output / "manifest.json", {
            "schema": "v6-parity-verification-v1", "complete": True,
            "pack": {"path": str(Path(args.pack).absolute()), "sha256": args.expected_sha256},
            "report_sha256": sha256(output / "verification.json"),
            "status": report["status"], "model_admission": False, "freeze_started": False})
    return {"operation": "verify", "written": args.run, "output": str(output),
            "status": report["status"], "pack_sha256": args.expected_sha256,
            "source_count": report["source_count"], "origin_authenticated": False,
            "model_admission": False, "freeze_started": False}


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    draft = sub.add_parser("prepare", help="generate an explicitly unreviewed pack and current capture checklist")
    draft.add_argument("--minimum-tick", type=float, required=True)
    draft.add_argument("--session-policy", choices=("strict", "source_literal"), default="source_literal")
    draft.add_argument("--vwap-mode", choices=("observed", "reset_flags"), default="observed")
    draft.set_defaults(action=prepare)
    check = sub.add_parser("verify", help="recompare all thirteen scopes from retained actual captures")
    check.add_argument("--pack", type=Path, required=True)
    check.add_argument("--expected-sha256", required=True)
    check.set_defaults(action=verify)
    for command in (draft, check):
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--run", action="store_true", help="write fresh local artifacts; default only previews")
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = args.action(args)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"V6-PARITY-PACK-FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
