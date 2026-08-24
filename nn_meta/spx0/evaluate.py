"""Nested, purged walk-forward for the spx0 pool — v4_evaluate's machinery
with the spx0 feature schema, a synthesized frozen spec (every proposal is
DTE 0, so the baseline is "take every filled proposal"), the pool's 25% DD
cap, and the mark stream the builder emits.

Run: ./venv/bin/python -m nn_meta.spx0.evaluate --folds 3 [--smoke]
     [--dataset nn_meta/artifacts_spx0/meta_dataset.parquet]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from nn_meta.mark_stream import load_mark_stream, mark_stream_path, option_b_blockers
from nn_meta.spx0 import config as sc
from nn_meta.temporal_validation import expanding_folds
from nn_meta.v4_artifacts import create_manifest, write_manifest
from nn_meta.v4_evaluate import _write_report, evaluate_window, schema_features


def synthetic_spec(ds: pd.DataFrame) -> dict:
    """Frozen spec for the spx0 pool: each (symbol, strategy)'s
    take-everything baseline variant. Round 4's seats carry no long-s50
    (code 0) rows, so the frozen dte per seat comes from
    ``sc.ROUND4_FROZEN`` when that code exists in the pair's data, else
    code 0 if present, else the pair's lowest code — never a code the
    dataset doesn't contain (an empty baseline would gate against nothing)."""
    frozen = getattr(sc, "ROUND4_FROZEN", {})
    syms: dict = {}
    for (sym, strat), grp in ds.groupby(["symbol", "strategy"]):
        codes = set(int(d) for d in grp["dte"].unique())
        pick = frozen.get(strat)
        if pick not in codes:
            pick = 0 if 0 in codes else sorted(codes)[0]
        syms.setdefault(sym, {"strategies": {}})["strategies"][strat] = {"dte": int(pick)}
    return {"symbols": syms, "config_hash": "spx0-seat-frozen"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=sc.DATASET)
    ap.add_argument("--marks", type=Path, default=None,
                    help="default: <dataset>.marks.parquet if present")
    ap.add_argument("--label", default="label_excess", choices=["label", "label_excess"])
    ap.add_argument("--models", default="nn,gbt")
    ap.add_argument("--seeds", default="0,1,2,3,4")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--gbt-estimators", type=int, default=600)
    ap.add_argument("--embargo", default="1D")
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.seeds, args.epochs, args.gbt_estimators = "0", 5, 50

    ds = pd.read_parquet(args.dataset)
    marks_path = args.marks or mark_stream_path(args.dataset)
    mark_stream = None
    if Path(marks_path).exists():
        blockers = option_b_blockers(ds.columns, mark_stream_exists=True)
        if blockers:
            raise SystemExit("spx0 dataset cannot support the ledger:\n  - " + "\n  - ".join(blockers))
        mark_stream = load_mark_stream(marks_path)
    spec = synthetic_spec(ds)
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    output = args.output or (sc.ARTIFACTS / "reports" / "spx0_walkforward_report.md")
    output.parent.mkdir(parents=True, exist_ok=True)

    results = []
    for i, window in enumerate(expanding_folds(ds["entry_ts"], n_folds=args.folds), 1):
        print(f"[spx0] nested fold {i}/{args.folds}", flush=True)
        results.append(evaluate_window(
            ds, window, spec=spec, schema="spx0", purged=True, label=args.label,
            models=models, seeds=seeds, epochs=args.epochs,
            gbt_estimators=args.gbt_estimators, embargo=args.embargo,
            mark_stream=mark_stream, dd_cap=sc.MAX_DRAWDOWN_CAP,
            thresholds=sc.KEEP_THRESHOLDS))
    _write_report(results, output)
    manifest = create_manifest(
        dataset_path=args.dataset, baseline_spec_path=args.dataset.parent / "build_manifest.json",
        feature_names=schema_features("spx0"),
        provider_metadata={"pool": "spx0", "interval": "1m", "dd_cap": sc.MAX_DRAWDOWN_CAP,
                           "mark_stream": str(marks_path) if mark_stream is not None else None},
        code_root=sc.DATA_CACHE.parent.parent)
    write_manifest(manifest, output.with_suffix(".manifest.json"))
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
