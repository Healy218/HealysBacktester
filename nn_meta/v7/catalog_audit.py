"""Read-only preflight and post-seal checks for the V7-2 compact catalog."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from nn_meta.multitimeframe_catalog import registered_catalog
from nn_meta.v7.storage import sha, verify

MINUTES = (5, 15, 30)
MIN_FREE_BYTES = 100 * 1024**3


def expected_variants() -> dict[int, list[dict]]:
    records = registered_catalog(["catalog-audit-probe"])["records"]
    return {minutes: [row for row in records if row["signal_minutes"] == minutes]
            for minutes in MINUTES}


def audit_store(base: Path, *, security_id: str, minutes: int,
                variants: list[dict], full: bool = False) -> dict:
    """Check exact catalog identity and receipts; full mode opens all batches."""
    feature_root, proposal_root = base / "features", base / "proposals"
    feature_header = verify(feature_root / "declaration")
    feature_summary = verify(feature_root / "summary")
    proposal_header = verify(proposal_root / "declaration")
    proposal_summary = verify(proposal_root / "summary")
    feature = json.loads((feature_root / "declaration" / "declaration.json").read_text())
    feature_report = json.loads((feature_root / "summary" / "report.json").read_text())
    proposal = json.loads((proposal_root / "declaration" / "declaration.json").read_text())
    proposal_report = json.loads((proposal_root / "summary" / "report.json").read_text())
    if (feature.get("security_id") != security_id or feature.get("minutes") != minutes or
            feature.get("variants") != variants or
            not feature.get("inputs") or not feature.get("sources") or
            feature.get("research_ready") is not False or
            feature_report.get("variants") != len(variants) or
            feature_report.get("full_timeframe_catalog") is not True or
            feature_report.get("source_and_input_guard") != "passed" or
            feature_report.get("storage_mode") != "compact-v1" or
            feature_report.get("research_ready") is not False):
        raise ValueError(f"{security_id}/{minutes}: feature scope/catalog mismatch")
    if (proposal.get("security_id") != security_id or
            proposal.get("variants") != variants or
            proposal.get("research_ready") is not False or
            Path(proposal.get("feature_store", "")).resolve() != feature_root.resolve() or
            proposal.get("feature_summary_sha256") != sha(feature_root / "summary" / "complete.json") or
            proposal_report.get("variants") != len(variants) or
            proposal_report.get("entry_filter_applied") is not True or
            proposal_report.get("research_ready") is not False):
        raise ValueError(f"{security_id}/{minutes}: proposal scope/catalog mismatch")
    if (feature_summary.get("parent_identity") != feature_header.get("identity") or
            feature_summary.get("basis_receipt_sha256") != sha(feature_root / "basis" / "complete.json") or
            proposal_header.get("identity") is None or proposal_summary.get("identity") is None):
        raise ValueError(f"{security_id}/{minutes}: store receipt chain mismatch")
    if full:
        from nn_meta.v7.proposal_store import StoredProposals
        stored = StoredProposals(proposal_root)
        if stored.report != proposal_report:
            raise ValueError(f"{security_id}/{minutes}: deep proposal report mismatch")
    return {"security_id": security_id, "minutes": minutes,
            "feature_receipt_sha256": sha(feature_root / "summary" / "complete.json"),
            "proposal_receipt_sha256": sha(proposal_root / "summary" / "complete.json"),
            "variants": len(variants), "proposals": proposal_report["proposals"]}


def audit_catalog(output: Path, security_ids: list[str], *, full: bool = False,
                  max_stores: int = 3) -> dict:
    """Pilot completed stores while building; full mode is post-seal only."""
    output = Path(output).resolve()
    if not output.is_dir() or not security_ids or len(set(security_ids)) != len(security_ids):
        raise ValueError("catalog output and unique expected security IDs are required")
    if max_stores < 1:
        raise ValueError("max_stores must be positive")
    from nn_meta.v7.rows import schema
    row_columns = len(schema())
    if row_columns != 221:
        raise ValueError(f"V7 downstream row schema changed: {row_columns} columns")
    variants = expected_variants()
    expected = {(sid, minutes) for sid in security_ids for minutes in MINUTES}
    present = {(sid, minutes) for sid, minutes in expected
               if (output / sid / str(minutes) / "proposals" / "summary" / "complete.json").is_file()}
    unknown = sorted(path.name for path in output.iterdir() if path.is_dir()
                     and path.name not in set(security_ids) and ".partial-" not in path.name)
    missing = sorted(expected - present)
    if full and (missing or unknown):
        raise ValueError(f"catalog is incomplete: {len(missing)} missing stores, {len(unknown)} unknown directories")
    selected = sorted(present) if full else sorted(present)[:max_stores]
    audited = [audit_store(output / sid / str(minutes), security_id=sid,
                           minutes=minutes, variants=variants[minutes], full=full)
               for sid, minutes in selected]
    free = shutil.disk_usage(output).free
    if full and free < MIN_FREE_BYTES:
        raise ValueError(f"catalog disk reserve below 100 GiB: {free}")
    return {"schema": "v7-catalog-audit-v1", "mode": "post-seal-full" if full else "live-preflight",
            "expected_securities": len(security_ids), "expected_stores": len(expected),
            "row_columns": row_columns,
            "present_stores": len(present), "missing_stores": len(missing),
            "unknown_directories": unknown, "audited_stores": len(audited),
            "audited_receipts": audited, "disk_free_bytes": free,
            "disk_reserve_100gib_passed": free >= MIN_FREE_BYTES,
            "technical_store_gate_passed": full and not missing and not unknown,
            "ready_for_7_3": False,
            "note": "Even a full technical pass requires separate resource/restart and scope review."}
