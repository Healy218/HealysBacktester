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
from nn_meta.providers import get_provider
from nn_meta import config
from nn_meta.baseline import freeze_symbol
from nn_meta.build_meta_dataset import (META_FEATURES, add_context_features,
                                        build_symbol_rows, join_surface_asof,
                                        load_surface_features)
from nn_meta.train_meta import run_one
from nn_meta.select_meta import (_EVALUATORS, all_rows, basket_buy_hold, fmt,
                                 frozen_mask, portfolio_metrics, predict_rows)

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
    ds = add_context_features(ds, surface)
    labeled = ds["net_return"].notna()
    ds["label"] = np.where(labeled, (ds["net_return"].fillna(0) > 0).astype(float),
                           np.nan)
    excess_ok = labeled & ds["und_period_return"].notna()
    ds["label_excess"] = np.where(
        excess_ok,
        (ds["net_return"].fillna(0) > ds["und_period_return"].fillna(0)).astype(float),
        np.nan)
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

    # 3) train the winning config only (same mode/label/arch as the main run)
    arch = [int(x) for x in winning["arch"].split("x")]
    mode = winning.get("mode", "filter")
    label_col = winning.get("label", "label")
    fold_spec = {"symbols": spec_symbols}
    rows_all = all_rows(ds, "test")
    if rows_all.empty:
        return {"fold": fold_i, "error": "no OOS trades"}
    fmask = frozen_mask(rows_all, fold_spec)
    oos_rows = rows_all[fmask].reset_index(drop=True) if mode == "filter" \
        else rows_all
    preds = []
    for seed in config.SEEDS:
        r = run_one(ds, arch, winning["lr"], seed, config.MAX_EPOCHS, label_col)
        preds.append(predict_rows(r["run_id"], oos_rows))
        print(f"  seed {seed}: val_loss={r['val_loss']:.4f}", flush=True)

    # 4) OOS: ensemble (winner's mode) vs fold-frozen baseline AND B&H
    ens = np.mean(preds, axis=0)
    nn = _EVALUATORS[mode](oos_rows, ens, winning["threshold"])
    base_pool = rows_all[fmask]
    base = portfolio_metrics(base_pool)
    bh = basket_buy_hold(fold_spec, oos_start, oos_end)
    nn_ret = nn["total_return"] if nn["total_return"] is not None else -np.inf
    beat_base = nn_ret > (base["total_return"] or -np.inf)
    beat_bh = nn_ret > bh
    print(f"  OOS: NN {fmt(nn['total_return'])} ({nn['n_kept']}/{nn['n_proposals']} kept, "
          f"ex-top3 {fmt(nn['total_ex_top3'])}) "
          f"vs baseline {fmt(base['total_return'])} ({base['n']}) "
          f"vs B&H {fmt(bh)} "
          f"→ {'beats both' if beat_base and beat_bh else 'beats baseline only' if beat_base else 'beats B&H only' if beat_bh else 'beats neither'}",
          flush=True)
    return {"fold": fold_i, "train_end": train_end,
            "oos": f"{oos_start}→{oos_end}",
            "n_symbols": len(spec_symbols),
            "nn_return": nn["total_return"], "nn_kept": nn["n_kept"],
            "nn_ex_top3": nn["total_ex_top3"],
            "base_return": base["total_return"], "base_n": base["n"],
            "bh_return": bh,
            "nn_beats": bool(beat_base), "nn_beats_bh": bool(beat_bh),
            "error": None}


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

    provider = get_provider()
    surface = load_surface_features()
    results = [run_fold(i + 1, *b, winning, provider, surface)
               for i, b in enumerate(fold_boundaries(args.folds))]

    ok = [r for r in results if not r.get("error")]
    wins = sum(r["nn_beats"] for r in ok)
    bh_wins = sum(r["nn_beats_bh"] for r in ok)
    both = sum(r["nn_beats"] and r["nn_beats_bh"] for r in ok)
    robust = bool(ok) and both > len(ok) / 2
    verdict = (f"NN filter beats the fold-frozen baseline in {wins}/{len(ok)} "
               f"folds and the underlying B&H basket in {bh_wins}/{len(ok)}; "
               f"both in {both}/{len(ok)} → "
               f"{'ROBUST' if robust else 'NOT robust'}")

    lines = ["", "## Walk-forward folds (everything re-frozen per fold)", "",
             "| fold | train end | OOS | NN return (kept) | NN ex-top3 | baseline | underlying B&H | NN wins |",
             "|---|---|---|---|---|---|---|---|"]
    for r in results:
        if r.get("error"):
            lines.append(f"| {r['fold']} | — | — | ERROR: {r['error']} | — | — | — | — |")
        else:
            marks = ("✅✅" if r["nn_beats"] and r["nn_beats_bh"]
                     else "✅❌" if r["nn_beats"] else "❌✅" if r["nn_beats_bh"]
                     else "❌❌")
            lines.append(
                f"| {r['fold']} | {r['train_end']} | {r['oos']} | "
                f"{fmt(r['nn_return'])} ({r['nn_kept']}) | "
                f"{fmt(r['nn_ex_top3'])} | "
                f"{fmt(r['base_return'])} ({r['base_n']}) | "
                f"{fmt(r['bh_return'])} | {marks} |")
    lines += ["", f"**{verdict}**",
              f"(OOS windows are thin — ~{len(_trading_days()) // (2 * args.folds)} "
              f"trading days each; treat single-fold results as noise-dominated)"]

    report = config.REPORTS_DIR / "meta_report.md"
    existing = report.read_text() if report.exists() else "# NN Meta Filter\n"
    report.write_text(existing + "\n".join(lines) + "\n")
    print(f"\n{verdict}\nappended to {report}")


if __name__ == "__main__":
    main()
