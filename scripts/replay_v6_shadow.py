"""Resolve recorded shadow decisions using externally anchored frozen exit plans.

Reads a consistent SQLite backup, never rewrites observations. Plan entry times
must match actual scoring observations; contract choices cannot be changed
after seeing outcomes. Exits need their own source receipts. Reports remain
research-only and use the same quote engine for candidate and frozen baseline.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3

import pandas as pd

from nn_meta.execution_validation import (QUOTE_SCENARIOS, QuoteTape, admit_fills,
    checked_ledger, replay_quotes, utc)
from nn_meta.training_jobs import sha
from nn_meta.v4_accounting import CostScenario
from scripts.validate_v6_execution import write


def run(database, legs, evidence, expected_evidence_sha256, output):
    output = Path(output).absolute()
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("shadow replay requires a fresh output directory without symlinks")
    if sha(evidence) != expected_evidence_sha256:
        raise ValueError("exit-plan evidence differs from external SHA256 anchor")
    ev = json.loads(Path(evidence).read_text())
    if (ev.get("legs_sha256") != sha(legs) or not ev.get("source_receipts")
            or ev.get("exit_policy") != "frozen-mechanical-signals"):
        raise ValueError("exit plans need frozen mechanical policy and bound source receipts")
    references = {str(Path(evidence).resolve()): expected_evidence_sha256, str(Path(legs).resolve()): sha(legs)}
    for ref in ev["source_receipts"]:
        path = Path(ref["path"])
        if not path.is_absolute():
            path = Path(evidence).parent / path
        if sha(path) != ref["sha256"]:
            raise ValueError("exit source receipt changed")
        references[str(path.resolve())] = ref["sha256"]
    output.mkdir(parents=True)
    snapshot = output / "observations.sqlite3"
    with sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(snapshot) as target:
            source.backup(target)
    with sqlite3.connect(snapshot) as db:
        scope = json.loads(db.execute("SELECT payload FROM scope WHERE id=1").fetchone()[0])
        candidates = db.execute("SELECT key,observed_at,candidate,baseline,payload FROM candidates").fetchall()
        quotes = [json.loads(r[0])["quote"] for r in db.execute("SELECT payload FROM quotes")]
    if not candidates or not quotes:
        raise ValueError("forward replay needs actual recorded candidates and quotes")
    source_rows = {key: (utc(at), bool(c), bool(b), json.loads(payload)["row"])
                   for key, at, c, b, payload in candidates}
    plans = pd.read_parquet(legs)
    if not {"trade_id", "exit_observed_at", "entry_decision_ts", "leg_index", "contract"} <= set(plans):
        raise ValueError("exit plans lack recorded decision/receipt identity")
    if not set(plans.trade_id) <= set(source_rows):
        raise ValueError("exit plan references an unobserved signal")
    for key, group in plans.groupby("trade_id"):
        observed, _, _, row = source_rows[key]
        first = group.sort_values("leg_index").iloc[0]
        contract = row.get("decision_contract")
        if (not contract or first.contract.removeprefix("O:") != contract.removeprefix("O:")
                or utc(first.entry_decision_ts) != observed):
            raise ValueError("exit plan changes the original selected contract or observed entry decision")
        for leg in group.itertuples(index=False):
            # Exit decisions are knowable at the recorded receipt, not at an
            # earlier bar start. The replay uses this actual decision clock.
            if utc(leg.exit_decision_ts) != utc(leg.exit_observed_at):
                raise ValueError("exit execution must use its actual observed decision timestamp")
    settings = scope.get("portfolio", {})
    maximum, fraction = settings.get("max_concurrent"), settings.get("position_fraction")
    if maximum is None or fraction is None:
        raise ValueError("shadow scope lacks a frozen portfolio budget")
    references[str(snapshot)] = sha(snapshot)
    frozen = {"schema": "v6-shadow-replay-v1", "inputs": references, "shadow_scope": scope,
        "scenarios": [asdict(p) for p in QUOTE_SCENARIOS], "research_only": True,
        "scanner_promotion": False,
        "sources": {str(Path(__file__).parents[1] / name): sha(Path(__file__).parents[1] / name)
            for name in ["scripts/replay_v6_shadow.py", "nn_meta/execution_validation.py",
                         "nn_meta/v4_accounting.py", "nn_meta/ev_sizing.py", "nn_meta/select_meta.py"]}}
    write(output / "scope.json", frozen)
    tape = QuoteTape(pd.DataFrame(quotes))
    result = {"schema": frozen["schema"], "research_only": True, "scanner_promotion": False,
        "selection": "recorded threshold/DTE decisions with actual-fill capacity; no replacements",
        "limitations": ["Unresolved signals are reported separately, not booked as zero-return trades.",
            "This report does not establish TradingView or provider/receipt parity.",
            "Fractional contracts and displayed-size screening do not establish market-impact capacity."],
        "policies": {}}
    for name, flag in (("candidate", 1), ("baseline", 2)):
        keys = [key for key, value in source_rows.items() if value[flag]]
        resolved = [key for key in keys if key in set(plans.trade_id)]
        selection = pd.DataFrame([{"trade_id": key, "symbol": source_rows[key][3]["symbol"],
                                    "signal_ts": source_rows[key][0]} for key in resolved],
                                 columns=["trade_id", "symbol", "signal_ts"])
        section = {"observed_selections": len(keys), "unresolved_selections": len(keys) - len(resolved), "scenarios": {}}
        if section["unresolved_selections"]:
            section["status"] = "incomplete_exit_coverage"
            result["policies"][name] = section
            continue
        if resolved:
            from nn_meta.ev_sizing import ev_selected_rows
            from nn_meta.select_meta import _portfolio_sim
            selection["entry_ts"] = selection.signal_ts.dt.tz_convert("UTC").dt.tz_localize(None)
            selection["exit_ts"] = [pd.to_datetime(plans.loc[plans.trade_id == key, "exit_decision_ts"], utc=True).max()
                                      for key in resolved]
            selection["exit_ts"] = selection.exit_ts.dt.tz_convert("UTC").dt.tz_localize(None)
            # Unbraked selection uses exit times and score shares, not outcome
            # returns. Zero here is solely a selection-helper placeholder.
            selection["net_return"] = 0.0
            selection["pred"] = [source_rows[key][3]["decision"] if name == "candidate" else 1.0 for key in resolved]
            if name == "candidate" and scope["bundle"]["mode"] == "ev":
                selection["pred_ev"] = selection.pred
                selection = ev_selected_rows(selection, maximum, fraction, dd_brake=None)
            else:
                _, _, entered = _portfolio_sim(selection, maximum, fraction)
                selection = selection.loc[[e[0] for e in entered]]
        section["reserved_positions"] = len(selection)
        section["reservation_policy"] = "frozen signal-time slots; failed fills do not backfill or reschedule reservations"
        for policy in QUOTE_SCENARIOS:
            if selection.empty:
                section["scenarios"][policy.name] = {"n_positions": 0, "total_return": None, "max_drawdown": None}
                continue
            tr, marks, audit = replay_quotes(selection, plans[plans.trade_id.isin(selection.trade_id)], tape, policy=policy)
            tr, marks, conflicts = admit_fills(tr, marks, max_concurrent=maximum)
            metrics, curve = checked_ledger(tr, marks, max_concurrent=maximum, position_fraction=fraction,
                costs=CostScenario(name=policy.name, fee=0, slippage=0), allow_unfunded=True)
            metrics.update(conservative_or_rejected_events=len(audit), capacity_rejected=len(conflicts))
            section["scenarios"][policy.name] = metrics
            curve.to_parquet(output / f"{name}_{policy.name}_equity.parquet", index=False)
            audit.to_csv(output / f"{name}_{policy.name}_audit.csv", index=False)
            conflicts.to_csv(output / f"{name}_{policy.name}_capacity.csv", index=False)
        result["policies"][name] = section
    for path, digest in {**references, **frozen["sources"]}.items():
        if sha(path) != digest:
            raise ValueError("shadow replay inputs changed")
    write(output / "results.json", result)
    write(output / "complete.json", {"research_only": True, "scanner_promotion": False,
        "outputs": {p.name: sha(p) for p in output.iterdir() if p.is_file()}})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--legs", type=Path, required=True)
    parser.add_argument("--exit-evidence", type=Path, required=True)
    parser.add_argument("--exit-evidence-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    run(a.database, a.legs, a.exit_evidence, a.exit_evidence_sha256, a.output)
    print(json.dumps({"output": str(a.output), "scanner_promotion": False}))


if __name__ == "__main__":
    main()
