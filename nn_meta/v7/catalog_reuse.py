"""Explicit, read-only compatibility proof for sealed V7 proposal stores."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
import json
from pathlib import Path

import pandas as pd

from nn_meta.v7.catalog_audit import MINUTES, audit_store, expected_variants
from nn_meta.v7.ordinary_actions import price_action
from nn_meta.v7.storage import sha

ROOT = Path(__file__).resolve().parents[2]
NONCOMPUTING_ADDITIONS = {
    str(ROOT / "nn_meta/v7/catalog_audit.py"),
    str(ROOT / "nn_meta/v7/catalog_reuse.py"),
}


def source_compatible(recorded: dict[str, str], current: dict[str, str]) -> bool:
    """Only audit code may have been added after a reusable store sealed."""
    if set(recorded) - set(current):
        return False
    if set(current) - set(recorded) - NONCOMPUTING_ADDITIONS:
        return False
    return all(current[name] == digest for name, digest in recorded.items())


def current_source_hashes() -> dict[str, str]:
    # Mirror build_features' captured source scope without changing that producer.
    directories = ("indicators", "signals", "portfolio", "utils", "nn_options_signal", "options")
    paths = {p for directory in directories for p in (ROOT / directory).rglob("*.py")}
    paths.update((ROOT / "nn_meta").glob("*.py"))
    paths.update((ROOT / "nn_meta/v7").glob("*.py"))
    paths.update((ROOT / "v3").glob("*.py"))
    paths.update((ROOT / "docs").rglob("*.pine"))
    paths.add(ROOT / "requirements.txt")
    paths.update((ROOT / "docs").rglob("*.json"))
    return {str(path): sha(path) for path in sorted(paths)}


def actions_by_security(path: Path) -> dict[str, list]:
    grouped = defaultdict(list)
    for event in json.loads((Path(path) / "actions.json").read_text()):
        grouped[event["security_id"]].append(price_action(event))
    return dict(grouped)


def declared_actions(actions: list, start: str, end: str) -> list[dict]:
    begin = pd.Timestamp(start)
    stop = pd.Timestamp(end)
    result = []
    for action in actions:
        if begin <= action.effective_at < stop:
            row = asdict(action)
            for key in ("effective_at", "available_at"):
                row[key] = row[key].isoformat()
            result.append(row)
    return result


def compatible_security(output: Path, security_id: str, actions: list,
                        *, old_action_sha: str, coverage_sha: str,
                        variants: dict | None = None,
                        current_sources: dict | None = None) -> dict | None:
    """Return sealed receipt hashes only if every timeframe is reusable unchanged.

    The old stores remain frozen. This proves computation-level equivalence for
    a single security; the catalog manifest records the cross-artifact bridge.
    """
    output = Path(output)
    variants = variants or expected_variants()
    current_sources = current_sources or current_source_hashes()
    receipts = {}
    for minutes in MINUTES:
        base = output / security_id / str(minutes)
        if not (base / "proposals/summary/complete.json").is_file():
            return None
        declaration = json.loads((base / "features/declaration/declaration.json").read_text())
        bound_old = [digest for name, digest in declaration["inputs"].items()
                     if name.endswith("/v7-ordinary-actions-20260918-7-2-current/actions.json")]
        if (bound_old != [old_action_sha]
                or declaration.get("action_coverage", {}).get("receipt_sha256") != coverage_sha
                or not source_compatible(declaration.get("sources", {}), current_sources)
                or declaration.get("actions") != declared_actions(actions,
                    declaration["start"], declaration["end"])):
            return None
        audited = audit_store(base, security_id=security_id, minutes=minutes,
                              variants=variants[minutes])
        receipts[str(minutes)] = {
            "feature": audited["feature_receipt_sha256"],
            "proposal": audited["proposal_receipt_sha256"],
        }
    return receipts


def check_admitted_actions(history: Path, actions: Path, coverage: Path) -> dict:
    """Preflight the exact selected history/event pair for all securities."""
    from nn_meta.v7.scope import HISTORY_START, HISTORY_END
    history = pd.read_parquet(Path(history) / "history.parquet",
                              columns=["security_id", "source_date", "source_status"])
    history = history[history.source_date.between(HISTORY_START, HISTORY_END)]
    observed = history[history.source_status.eq("observed")].groupby("security_id").source_date.agg(["min", "max"])
    history = history.join(observed, on="security_id")
    history = history[history.source_date.between(history["min"], history["max"])]
    panel = pd.read_parquet(Path(coverage) / "coverage.parquet",
                            columns=["security_id", "source_date", "history_admitted", "event_id"])
    panel = panel.merge(history[["security_id", "source_date"]],
                        on=["security_id", "source_date"], how="inner", validate="one_to_one")
    panel = panel[panel.history_admitted.astype(bool)]
    dates = set(panel[["security_id", "source_date"]].itertuples(index=False, name=None))
    actual = set(panel[["security_id", "event_id"]].dropna().itertuples(index=False, name=None))
    events = json.loads((Path(actions) / "actions.json").read_text())
    expected = {(event["security_id"], event["action"]["event_id"])
                for event in events if (event["security_id"],
                    pd.Timestamp(event["action"]["effective_at"]).tz_convert("America/New_York")
                        .date().isoformat()) in dates}
    if actual != expected:
        raise ValueError(f"Action/coverage preflight mismatch: "
                         f"{len(expected - actual)} missing and {len(actual - expected)} extra events")
    return {"securities": history.security_id.nunique(), "admitted_events": len(actual),
            "actions_sha256": sha(Path(actions) / "actions.json"),
            "coverage_sha256": sha(Path(coverage) / "complete.json")}


def verify_reuse_manifest(path: Path, *, output: Path, actions: Path,
                          coverage: Path) -> dict:
    document = json.loads(Path(path).read_text())
    if (document.get("schema") != "v7-catalog-reuse-v1"
            or Path(document["output"]).resolve() != Path(output).resolve()
            or document["new_actions_sha256"] != sha(Path(actions) / "actions.json")
            or document["coverage_sha256"] != sha(Path(coverage) / "complete.json")):
        raise ValueError("V7 reuse manifest is bound to different catalog inputs")
    old_actions = Path(document["old_actions"])
    if document["old_actions_sha256"] != sha(old_actions / "actions.json"):
        raise ValueError("V7 old action parent changed")
    grouped = actions_by_security(actions)
    variants = expected_variants()
    current_sources = current_source_hashes()
    for security_id, receipts in document["securities"].items():
        actual = compatible_security(output, security_id, grouped.get(security_id, []),
            old_action_sha=document["old_actions_sha256"],
            coverage_sha=document["coverage_sha256"], variants=variants,
            current_sources=current_sources)
        if actual != receipts:
            raise ValueError(f"V7 reuse proof changed: {security_id}")
    return document
