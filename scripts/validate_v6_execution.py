"""Revalidate a frozen final V6 selection against its same-window baseline.

Writes only a fresh output directory. Never trains, selects a new threshold,
edits a campaign, deploys, or sends notifications. The final validation tail
is selection/revalidation, not a new holdout. Quote replay is optional and
explicitly incomplete until a provenance-bound tape and any roll plans exist.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
import pandas as pd

from nn_meta.execution_validation import (QUOTE_SCENARIOS, QuoteTape,
    aggregate_latency, admit_fills, checked_ledger, replay_quotes)
from nn_meta.training_jobs import sha
from nn_meta.v4_accounting import CostScenario


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def frozen_selections(campaign):
    from nn_meta import config
    from nn_meta.mark_stream import stable_trade_id
    from nn_meta.select_meta import frozen_mask
    from nn_meta.v4_evaluate import _candidate_rows, _selected_rows

    model = json.loads((campaign / "model_final/ensemble_config.json").read_text())
    spec = json.loads((campaign / "artifacts/baseline_spec.json").read_text())
    if (not np.isfinite(model["threshold"]) or model["mode"] not in {"ev", "rank", "filter"}
            or model.get("feature_contract_version") != config_feature_contract()):
        raise ValueError("frozen policy differs from the configured V6 contract")
    predictions = pd.read_parquet(campaign / "reports/finalize_val_predictions.parquet")
    if predictions.empty or predictions.trade_id.duplicated().any():
        raise ValueError("predictions must have a unique nonempty frozen population")
    score = predictions["ev_ensemble" if model["mode"] == "ev" else "pred_ensemble"].to_numpy()
    if not np.isfinite(score).all():
        raise ValueError("frozen predictions contain non-finite values")
    candidate = _selected_rows(_candidate_rows(predictions, score, model["mode"],
                                               model["threshold"]), model["mode"],
                               dd_brake=model.get("dd_brake"))
    baseline = _selected_rows(predictions.loc[frozen_mask(predictions, spec)].assign(pred=1.0), "filter")
    needed = set(candidate.trade_id) | set(baseline.trade_id)
    columns = ["symbol", "strategy", "trade_idx", "dte", "entry_ts", "exit_ts",
        "fill_entry_ts", "fill_exit_ts", "gross_return", "n_fills", "contract", "expiration"]
    rows = pd.read_parquet(campaign / "artifacts/meta_dataset.parquet", columns=columns,
        filters=[("entry_ts", ">=", predictions.entry_ts.min()),
                 ("entry_ts", "<=", predictions.entry_ts.max())])
    rows["trade_id"] = stable_trade_id(rows).to_numpy()
    rows = rows.loc[rows.trade_id.isin(needed)]
    if rows.trade_id.duplicated().any() or set(rows.trade_id) != needed:
        raise ValueError("frozen selections do not uniquely match dataset execution rows")
    selections = {}
    for name, selected in (("candidate", candidate), ("baseline", baseline)):
        metadata = selected[["trade_id"] + (["size_fraction"] if "size_fraction" in selected else [])]
        selections[name] = metadata.merge(rows, on="trade_id", validate="one_to_one")
    return selections, {"mode": model["mode"], "threshold": model["threshold"],
        "dd_brake": model.get("dd_brake"), "family": model["family"],
        "max_concurrent": config.MAX_CONCURRENT, "position_fraction": config.PORTFOLIO_FRACTION,
        "population_rows": len(predictions), "start": predictions.entry_ts.min().isoformat(),
        "end": predictions.entry_ts.max().isoformat(),
        "basis": "final selection/revalidation; overlapping prior tests; not a fresh holdout",
        "sizing": "frozen original-policy allocations; counterfactual exits do not retune the drawdown brake",
        "rejected_entries_backfilled": False}


def config_feature_contract():
    from nn_meta.feature_contract import CONTRACT_VERSION
    return CONTRACT_VERSION


def single_legs(selected):
    """Aggregate labels identify only the initial contract; rolls need a leg export."""
    from options.data.provider import parse_occ_symbol
    if (selected.n_fills != 1).any():
        raise ValueError("rolled positions require explicit frozen per-leg plans")
    out = selected[["trade_id", "contract"]].copy()
    out["leg_index"] = 0
    out["entry_decision_ts"] = pd.to_datetime(selected.entry_ts, utc=True) + pd.Timedelta(minutes=15)
    out["exit_decision_ts"] = pd.to_datetime(selected.exit_ts, utc=True) + pd.Timedelta(minutes=15)
    out["expiration_ts"] = [pd.Timestamp(f"{parse_occ_symbol(c.removeprefix('O:'))[1]} 16:00",
                                                       tz="America/New_York").tz_convert("UTC")
                             for c in selected.contract]
    return out


def run(campaign, output, *, quotes=None, quote_evidence=None, legs=None):
    from nn_meta import config
    from nn_meta.mark_stream import execution_frames, load_mark_stream, mark_stream_path
    campaign, output = Path(campaign).resolve(), Path(output).absolute()
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("execution validation output must be fresh without symlinks")
    if output.is_relative_to(campaign):
        raise ValueError("preserve the completed campaign; write validation outside it")
    files = [campaign / p for p in ["model_final/ensemble_config.json",
        "reports/finalize_val_predictions.parquet", "artifacts/baseline_spec.json",
        "artifacts/meta_dataset.parquet"]]
    mark_path = mark_stream_path(files[-1]); files.append(mark_path)
    # Bind revalidation to the preserved successful campaign receipts, not
    # merely to whatever bytes happen to occupy those filenames today.
    receipt_paths = [campaign / "runs/continuation" / f"{stage}.json"
                     for stage in ("assemble", "finalize")]
    receipts = [json.loads(p.read_text()) for p in receipt_paths]
    if any(r.get("returncode") != 0 or not r.get("outputs") for r in receipts):
        raise ValueError("revalidation requires completed assembly and finalization receipts")
    recorded = {name: digest for receipt in receipts for name, digest in receipt["outputs"].items()}
    original_scope = campaign / "continuation_scope.json"
    recorded.update(json.loads(original_scope.read_text())["inputs"])
    for path in files:
        suffix = "/" + path.relative_to(campaign).as_posix()
        hashes = {digest for name, digest in recorded.items() if name.endswith(suffix)}
        if hashes != {sha(path)}:
            raise ValueError(f"completed campaign receipt disagrees with {path.name}")
    files.extend([*receipt_paths, original_scope])
    tape = None
    if quotes:
        if not quote_evidence:
            raise ValueError("quote tape requires a source/availability evidence JSON")
        evidence = json.loads(Path(quote_evidence).read_text())
        if (evidence.get("quotes_sha256") != sha(quotes)
                or evidence.get("availability_basis") not in {"receipt", "sip"}
                or not evidence.get("source") or not evidence.get("coverage_limitations")):
            raise ValueError("quote evidence needs a matching tape hash, source, clock basis and coverage limitations")
        files.extend([Path(quotes), Path(quote_evidence)])
        tape = QuoteTape(pd.read_parquet(quotes))
    if legs:
        if tape is None:
            raise ValueError("leg plans require a quote tape")
        files.append(Path(legs))
    inputs = {str(p): sha(p) for p in files}
    selections, policy = frozen_selections(campaign)
    if tape is not None and policy["dd_brake"] is not None:
        raise ValueError("DD-braked quote policies require a causal quote-ledger sizing replay")
    output.mkdir(parents=True)
    costs = [CostScenario(), CostScenario(name="spread_25bps", half_spread_bps=25),
             CostScenario(name="spread_50bps", half_spread_bps=50),
             CostScenario(name="spread_100bps", fee=.002, slippage=.001, half_spread_bps=100)]
    scope = {"schema": "v6-execution-validation-v1", "inputs": inputs,
        "frozen_policy": policy, "aggregate_costs": [asdict(c) for c in costs],
        "latency_limits_seconds": [60, 300, 900],
        "quote_scenarios": [asdict(q) for q in QUOTE_SCENARIOS],
        "research_only": True, "scanner_promotion": False,
        "sources": {str(Path(__file__).parents[1] / name): sha(Path(__file__).parents[1] / name)
            for name in ["scripts/validate_v6_execution.py", "nn_meta/execution_validation.py",
                         "nn_meta/v4_accounting.py", "nn_meta/v4_evaluate.py", "nn_meta/select_meta.py",
                         "nn_meta/ev_sizing.py", "nn_meta/mark_stream.py", "nn_meta/config.py"]}}
    write(output / "scope.json", scope)
    ids = set().union(*(set(f.trade_id) for f in selections.values()))
    marks = load_mark_stream(mark_path, trade_ids=ids)
    results = {"schema": scope["schema"], "research_only": True,
               "scanner_promotion": False, "complete": False, "policies": {},
               "limitations": [policy["basis"], "Fixed selected positions; rejected fills do not backfill slots.",
                   policy["sizing"],
                   "Aggregate spread scenarios are sensitivity analysis, not observed bid/ask fills."]}
    if tape is None:
        results["limitations"].append("Executable quote replay unavailable: supply a tape and evidence; no quote results inferred from bars.")
    else:
        results["limitations"].append("Quote marks use observed events plus weekday RTH cadence; calendar/session coverage is not certified.")
        results["limitations"].append("Fractional contract sizing; displayed size is screened positive but not a market-impact/capacity proof.")
        results["quote_evidence"] = evidence
    for name, selected in selections.items():
        selected.to_parquet(output / f"{name}_selected.parquet", index=False)
        trades, stream = execution_frames(selected, marks)
        section = {"selected_positions": len(selected), "aggregate": {}, "quotes": {}}
        for limit in [None, *scope["latency_limits_seconds"]]:
            label = "retained_fills" if limit is None else f"max_delay_{limit}s"
            retained, observed = trades, stream
            rejected = pd.DataFrame()
            if limit is not None:
                retained, observed, rejected = aggregate_latency(trades, stream, max_delay_seconds=limit)
                rejected.to_csv(output / f"{name}_{label}_rejections.csv", index=False)
            retained, observed, conflicts = admit_fills(retained, observed, max_concurrent=config.MAX_CONCURRENT)
            conflicts.to_csv(output / f"{name}_{label}_capacity_rejections.csv", index=False)
            section["aggregate"][label] = {"rejected": len(rejected), "capacity_rejected": len(conflicts), "costs": {}}
            for cost in costs:
                metrics, curve = checked_ledger(retained, observed,
                    max_concurrent=config.MAX_CONCURRENT, position_fraction=config.PORTFOLIO_FRACTION, costs=cost,
                    allow_unfunded=True)
                section["aggregate"][label]["costs"][cost.name] = metrics
                curve.to_parquet(output / f"{name}_{label}_{cost.name}_equity.parquet", index=False)
        if tape is not None:
            leg_frame = pd.read_parquet(legs) if legs else single_legs(selected)
            leg_frame = leg_frame[leg_frame.trade_id.isin(selected.trade_id)]
            if not leg_frame.groupby("trade_id").size().reindex(selected.trade_id).eq(selected.n_fills.to_numpy()).all():
                raise ValueError("quote leg count disagrees with frozen execution; no omitted rolls")
            plans = selected[["trade_id", "symbol"] + (["size_fraction"] if "size_fraction" in selected else [])].copy()
            plans["signal_ts"] = pd.to_datetime(selected.entry_ts, utc=True) + pd.Timedelta(minutes=15)
            for quote_policy in QUOTE_SCENARIOS:
                qt, qm, audit = replay_quotes(plans, leg_frame, tape, policy=quote_policy)
                qt, qm, conflicts = admit_fills(qt, qm, max_concurrent=config.MAX_CONCURRENT)
                metrics, curve = checked_ledger(qt, qm, max_concurrent=config.MAX_CONCURRENT,
                    position_fraction=config.PORTFOLIO_FRACTION,
                    costs=CostScenario(name=quote_policy.name, fee=0, slippage=0), allow_unfunded=True)
                metrics["conservative_or_rejected_events"] = len(audit)
                metrics["capacity_rejected"] = len(conflicts)
                section["quotes"][quote_policy.name] = metrics
                audit.to_csv(output / f"{name}_{quote_policy.name}_audit.csv", index=False)
                conflicts.to_csv(output / f"{name}_{quote_policy.name}_capacity_rejections.csv", index=False)
                curve.to_parquet(output / f"{name}_{quote_policy.name}_equity.parquet", index=False)
        results["policies"][name] = section
    for p, digest in {**inputs, **scope["sources"]}.items():
        if sha(p) != digest:
            raise ValueError(f"validation input/source changed: {p}")
    results["complete"] = True
    write(output / "results.json", results)
    write(output / "complete.json", {"scope_sha256": sha(output / "scope.json"),
        "outputs": {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()},
        "research_only": True, "quote_replay_run": tape is not None, "scanner_promotion": False})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quotes", type=Path)
    parser.add_argument("--quote-evidence", type=Path)
    parser.add_argument("--legs", type=Path)
    args = parser.parse_args()
    result = run(args.campaign_root, args.output, quotes=args.quotes,
                 quote_evidence=args.quote_evidence, legs=args.legs)
    print(json.dumps({"output": str(args.output), "complete": result["complete"],
                      "scanner_promotion": False}))


if __name__ == "__main__":
    main()
