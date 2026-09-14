"""Bounded V6 validation/shadow tables for the private Training report.

Standalone publisher module: stdlib only, no model imports or raw-data reads.
Directories must be explicitly configured inside the research checkout.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

LIMIT = 1_000_000


def read(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError("V6 follow-up input exceeds size limit")
    def reject(value):
        raise ValueError(f"non-finite follow-up JSON: {value}")
    return json.loads(raw, parse_constant=reject), raw


def directory(root, configured):
    base = Path(configured)
    if not base.is_absolute():
        base = root / base
    if any(p.is_symlink() for p in (base, *base.parents)) or not base.resolve().is_relative_to(root.resolve()):
        raise ValueError("V6 evidence must stay inside the research checkout without symlinks")
    return base


def percent(value):
    return "—" if value is None else f"{value * 100:+.1f}%"


def append_followup(root, report, *, execution=None, shadow=None, now=None):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    if execution:
        base = directory(root, execution)
        receipt, _ = read(base / "complete.json")
        result, raw = read(base / "results.json")
        scope, scope_raw = read(base / "scope.json")
        if (receipt.get("outputs", {}).get("results.json") != hashlib.sha256(raw).hexdigest()
                or receipt.get("outputs", {}).get("scope.json") != hashlib.sha256(scope_raw).hexdigest()
                or result.get("complete") is not True or result.get("research_only") is not True
                or result.get("scanner_promotion") is not False):
            raise ValueError("V6 execution report failed receipt/research binding")
        # Never append a different campaign's validation to this report.
        source = str((root / "nn_meta/campaigns" / report["campaign"] / "v6/model_final/ensemble_config.json").resolve())
        if source not in scope["inputs"]:
            raise ValueError("execution validation belongs to a different training campaign")
        _, model_raw = read(source)
        if hashlib.sha256(model_raw).hexdigest() != scope["inputs"][source]:
            raise ValueError("execution validation model no longer matches")
        rows = []
        for side in ("candidate", "baseline"):
            for latency, section in result["policies"][side]["aggregate"].items():
                for name, metric in section["costs"].items():
                    rows.append([side.title(), latency.replace("_", " "), name.replace("_", " "),
                        str(metric["n_positions"]), percent(metric["total_return"]),
                        percent(metric["max_drawdown"]), "Matched" if metric["independent_ledger_match"] else "Failed"])
        report["tables"].append(dict(title="Frozen execution revalidation", columns=["Policy", "Fill delay", "Costs",
            "Positions", "Return", "Max drawdown", "Independent ledger"], rows=rows,
            note="Final selection/revalidation tail, not a fresh holdout. Fixed selections; rejected fills do not backfill slots. Aggregate spread costs are assumptions, not observed quotes."))
        report["notes"].extend(result["limitations"])
        report["sources"].append(dict(path=str((base / "results.json").relative_to(root)),
            sha256=hashlib.sha256(raw).hexdigest(), content=raw.decode(), excerpt=False))
    if shadow:
        base = directory(root, shadow)
        result, _ = read(base / "summary.json")
        if (result.get("schema") != "v6-shadow-summary-v1" or result.get("research_only") is not True
                or result.get("scanner_promotion") is not False):
            raise ValueError("invalid V6 shadow summary")
        _, model_raw = read(root / "nn_meta/campaigns" / report["campaign"] / "v6/model_final/ensemble_config.json")
        if result.get("bundle_sha256") != hashlib.sha256(model_raw).hexdigest():
            raise ValueError("shadow observations belong to a different model")
        observed = result.get("last_pass_at")
        stale = True
        if observed:
            stamp = datetime.fromisoformat(observed.replace("Z", "+00:00"))
            stale = stamp.tzinfo is None or not 0 <= (now - stamp).total_seconds() <= 1800
        report["tables"].append(dict(title="Forward shadow observations", columns=["Measure", "Value"],
            rows=[["Status", "Stale / no recent pass" if stale else "Recording · research only"],
                  ["Last pass", observed or "—"], ["Signals", str(result["signals"])],
                  ["Candidate selections", str(result["candidate_selections"])],
                  ["Baseline selections", str(result["baseline_selections"])],
                  ["Quote observations", str(result["quote_observations"])],
                  ["Failed passes", str(result["failed_passes"])],
                  ["Execution", result["execution_status"]]],
            note="Selections are recorded signals, not executed positions. Missing realized returns remain unavailable."))
        report["notes"].extend(result["limitations"])
    return report
