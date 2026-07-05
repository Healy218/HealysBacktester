# nn_meta/walkforward_meta.py
"""Walk-forward robustness check: NN-filtered vs frozen baseline, per fold.

K expanding date-based folds over the data window (pattern mirrors
backtests/run_walkforward.py, but by calendar date because everything here is
symbol-pooled). Per fold, EVERYTHING re-derives from fold-train only:
  1. Re-freeze the baseline per symbol on [WINDOW_START, fold_train_end].
  2. Build meta-labels on fold-train; the last VAL_FRACTION of its dates is
     the fold's early-stopping/validation slice.
  3. Train ONLY the main run's winning config (arch/lr/threshold from
     model_final/ensemble_config.json) across seeds.
  4. Evaluate NN-filtered vs fold-frozen baseline on the fold's OOS window.

Verdict: the NN filter is robust if it beats the baseline in a MAJORITY of
folds. Appends the per-fold table to reports/meta_report.md.

Run:  python -m nn_meta.walkforward_meta [--folds 3]
"""
import argparse
import json
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import numpy as np
import pandas as pd

from utils.logging_utils import setup_logging
from options.data.hybrid_provider import HybridCachedProvider
from nn_meta import config
from nn_meta.baseline import equity_metrics, freeze_symbol
from nn_meta.build_meta_dataset import (META_FEATURES, build_symbol_rows,
                                        join_surface_asof, load_surface_features)
from nn_meta.train_meta import run_one
from nn_meta.select_meta import evaluate_filter, fmt, frozen_rows, predict_rows

logger = setup_logging(log_file="logs/backtester.log")

_TAG = "NN-META-WF"

MIN_TRAIN_PCT = 0.5
VAL_FRACTION = 0.2          # tail of fold-train used as the fold's val slice


def _trading_days() -> pd.DatetimeIndex:
    panel = pd.read_parquet(config.UNDERLYING_15M_PARQUET,
                            columns=["symbol", "timestamp"])
    days = pd.DatetimeIndex(panel["timestamp"]).normalize().unique().sort_values()
    return days[(days >= config.WINDOW_START) & (days <= config.WINDOW_END)]


def fold_boundaries(n_folds: int) -> list[tuple[str, str, str]]:
    """[(train_end, oos_start, oos_end)] by calendar date, expanding train."""
    days = _trading_days()
    n = len(days)
    oos_size = int(n * (1 - MIN_TRAIN_PCT) / n_folds)
    out = []
    for k in range(n_folds):
        i_end = int(n * MIN_TRAIN_PCT) + k * oos_size
        j_end = min(i_end + oos_size, n) - 1
        if j_end <= i_end:
            break
        out.append((days[i_end - 1].date().isoformat(),
                    days[i_end].date().isoformat(),
                    days[j_end].date().isoformat()))
    return out


def _fold_dataset(spec_symbols: dict, provider, window_end: str,
                  surface: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for sym, entry in spec_symbols.items():
        df = build_symbol_rows(sym, entry, provider,
                               window_start=config.WINDOW_START,
                               window_end=window_end)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    ds = pd.concat(frames, ignore_index=True)
    ds = join_surface_asof(ds, surface)
    ds["label"] = np.where(ds["net_return"].notna(),
                           (ds["net_return"].fillna(0) > 0).astype(float), np.nan)
    return ds


def run_fold(fold_i: int, train_end: str, oos_start: str, oos_end: str,
             winning: dict, provider, surface: pd.DataFrame) -> dict:
    print(f"\n─ fold {fold_i}: train →{train_end}, OOS {oos_start}→{oos_end}",
          flush=True)

    # 1) re-freeze per symbol on fold-train
    spec_symbols = {}
    for sym in config.UNDERLYINGS:
        try:
            entry = freeze_symbol(sym, provider,
                                  train_start=config.WINDOW_START,
                                  train_end=train_end)
        except Exception as e:
            logger.exception(f"[{_TAG}] fold {fold_i} {sym}: freeze failed: {e}")
            entry = None
        if entry is not None:
            spec_symbols[sym] = entry
    print(f"  frozen {len(spec_symbols)} symbols", flush=True)
    if not spec_symbols:
        return {"fold": fold_i, "error": "no freezable symbols"}

    # 2) labels over fold-train AND the OOS window (one build; split below)
    ds = _fold_dataset(spec_symbols, provider, oos_end, surface)
    if ds.empty:
        return {"fold": fold_i, "error": "no dataset rows"}
    d = ds["entry_date"]
    tr_days = d[d <= train_end].sort_values().unique()
    val_cut = tr_days[int(len(tr_days) * (1 - VAL_FRACTION))] if len(tr_days) else None
    ds["split"] = np.select(
        [d < val_cut, (d >= val_cut) & (d <= train_end),
         (d >= oos_start) & (d <= oos_end)],
        ["train", "val", "test"], default="purged")
    ds = ds[ds["split"] != "purged"].reset_index(drop=True)

    # 3) train the winning config only
    arch = [int(x) for x in winning["arch"].split("x")]
    fold_spec = {"symbols": spec_symbols}
    preds, seeds_used = [], []
    oos_rows = frozen_rows(ds, fold_spec, "test")
    if oos_rows.empty:
        return {"fold": fold_i, "error": "no OOS trades"}
    for seed in config.SEEDS:
        r = run_one(ds, arch, winning["lr"], seed, config.MAX_EPOCHS)
        preds.append(predict_rows(r["run_id"], oos_rows))
        seeds_used.append(seed)
        print(f"  seed {seed}: val_loss={r['val_loss']:.4f}", flush=True)

    # 4) OOS: ensemble filter vs fold-frozen baseline
    ens = np.mean(preds, axis=0)
    nn = evaluate_filter(oos_rows, ens, winning["threshold"])
    base = equity_metrics(oos_rows["net_return"].tolist())
    beat = (nn["total_return"] or -np.inf) > (base["total_return"] or -np.inf)
    print(f"  OOS: NN {fmt(nn['total_return'])} ({nn['n_kept']}/{nn['n_proposals']} kept) "
          f"vs baseline {fmt(base['total_return'])} ({base['n']}) "
          f"→ {'NN WINS' if beat else 'baseline wins'}", flush=True)
    return {"fold": fold_i, "train_end": train_end,
            "oos": f"{oos_start}→{oos_end}",
            "n_symbols": len(spec_symbols),
            "nn_return": nn["total_return"], "nn_kept": nn["n_kept"],
            "base_return": base["total_return"], "base_n": base["n"],
            "nn_beats": bool(beat), "error": None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=3)
    args = ap.parse_args()

    config.ensure_dirs()
    ens_path = config.MODEL_FINAL_DIR / "ensemble_config.json"
    if not ens_path.exists():
        raise SystemExit("run select_meta first — walk-forward retrains the "
                         "winning config only")
    winning = json.loads(ens_path.read_text())

    provider = HybridCachedProvider()
    surface = load_surface_features()
    results = [run_fold(i + 1, *b, winning, provider, surface)
               for i, b in enumerate(fold_boundaries(args.folds))]

    ok = [r for r in results if not r.get("error")]
    wins = sum(r["nn_beats"] for r in ok)
    verdict = (f"NN filter beats the fold-frozen baseline in {wins}/{len(ok)} "
               f"folds → {'ROBUST' if ok and wins > len(ok) / 2 else 'NOT robust'}")

    lines = ["", "## Walk-forward folds (everything re-frozen per fold)", "",
             "| fold | train end | OOS | NN return (kept) | baseline | NN wins |",
             "|---|---|---|---|---|---|"]
    for r in results:
        if r.get("error"):
            lines.append(f"| {r['fold']} | — | — | ERROR: {r['error']} | — | — |")
        else:
            lines.append(
                f"| {r['fold']} | {r['train_end']} | {r['oos']} | "
                f"{fmt(r['nn_return'])} ({r['nn_kept']}) | "
                f"{fmt(r['base_return'])} ({r['base_n']}) | "
                f"{'✅' if r['nn_beats'] else '❌'} |")
    lines += ["", f"**{verdict}**",
              f"(OOS windows are thin — ~{len(_trading_days()) // (2 * args.folds)} "
              f"trading days each; treat single-fold results as noise-dominated)"]

    report = config.REPORTS_DIR / "meta_report.md"
    existing = report.read_text() if report.exists() else "# NN Meta Filter\n"
    report.write_text(existing + "\n".join(lines) + "\n")
    print(f"\n{verdict}\nappended to {report}")


if __name__ == "__main__":
    main()
