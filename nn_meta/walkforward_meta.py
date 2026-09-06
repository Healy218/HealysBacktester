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

Every long stage checkpoints under artifacts/wf/ (per-symbol freeze, per-symbol
dataset rows, per-seed OOS predictions, per-fold results) so an interrupted run
resumes where it stopped. --reuse-runs accepts fold numbers whose runs/ model
dirs are known-good from a previous interrupted run of the SAME fold (skips
retraining and predicts from them); never list a fold whose runs/ dirs were
overwritten by a different fold's training.

Run:  python -m nn_meta.walkforward_meta [--folds 3] [--reuse-runs 1[,2]]
"""
import argparse
import json
import os
import hashlib

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
from nn_meta.temporal_validation import assign_purged_splits
from nn_meta.feature_contract import CONTRACT_VERSION
from nn_meta.wf_context import experiment_key, frame_digest
from nn_meta.select_meta import (_EVALUATORS, all_rows, basket_buy_hold, fmt,
                                 frozen_mask, portfolio_metrics, predict_rows)

logger = setup_logging(log_file="logs/backtester.log")

_TAG = "NN-META-WF"

MIN_TRAIN_PCT = 0.5
VAL_FRACTION = 0.2          # tail of fold-train used as the fold's val slice

WF_DIR = config.ARTIFACTS / "wf"           # resume checkpoints (delete to redo)



def fold_splits(ds: pd.DataFrame, train_end: str, oos_start: str, oos_end: str) -> pd.Series:
    days = pd.to_datetime(ds["entry_ts"]).dt.normalize()
    tr_days = days[days <= pd.Timestamp(train_end)].sort_values().unique()
    if not len(tr_days):
        raise ValueError("fold has no training dates")
    val_cut = tr_days[int(len(tr_days) * (1 - VAL_FRACTION))]
    return assign_purged_splits(ds, train_start=config.WINDOW_START, val_start=val_cut,
                                test_start=oos_start, test_end=oos_end, embargo="1D")


def _json_default(o):
    return o.item() if hasattr(o, "item") else float(o)


def _save_json(path, obj) -> None:
    path.write_text(json.dumps(obj, default=_json_default))


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
                  surface: pd.DataFrame, rows_dir) -> pd.DataFrame:
    rows_dir.mkdir(parents=True, exist_ok=True)
    done_path = rows_dir / "done.json"
    done = set(json.loads(done_path.read_text())) if done_path.exists() else set()
    frames = []
    for sym, entry in spec_symbols.items():
        pq = rows_dir / f"{sym}.parquet"
        if sym in done:
            if pq.exists():
                frames.append(pd.read_parquet(pq))
            continue
        df = build_symbol_rows(sym, entry, provider,
                               window_start=config.WINDOW_START,
                               window_end=window_end)
        if not df.empty:
            df.to_parquet(pq, index=False)
            frames.append(df)
        done.add(sym)
        _save_json(done_path, sorted(done))
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
             winning: dict, provider, surface: pd.DataFrame,
             reuse_runs: bool = False, membership: bool = False) -> dict:
    print(f"\n─ fold {fold_i}: train →{train_end}, OOS {oos_start}→{oos_end}",
          flush=True)

    # 1) re-freeze per symbol on fold-train (checkpointed per symbol)
    spec_path = WF_DIR / f"fold{fold_i}_spec.json"
    state = json.loads(spec_path.read_text()) if spec_path.exists() \
        else {"attempted": [], "symbols": {}}
    spec_symbols = state["symbols"]
    for sym in config.UNDERLYINGS:
        if sym in state["attempted"]:
            continue
        try:
            entry = freeze_symbol(sym, provider,
                                  train_start=config.WINDOW_START,
                                  train_end=train_end)
        except Exception as e:
            logger.exception(f"[{_TAG}] fold {fold_i} {sym}: freeze failed: {e}")
            entry = None
        if entry is not None:
            spec_symbols[sym] = entry
        state["attempted"].append(sym)
        _save_json(spec_path, state)
    print(f"  frozen {len(spec_symbols)} symbols", flush=True)
    if not spec_symbols:
        return {"fold": fold_i, "error": "no freezable symbols"}

    # 2) labels over fold-train AND the OOS window (one build; split below)
    ds_path = WF_DIR / f"fold{fold_i}_dataset.parquet"
    if ds_path.exists():
        ds = pd.read_parquet(ds_path)
        print(f"  dataset: resumed {len(ds)} rows from checkpoint", flush=True)
    else:
        ds = _fold_dataset(spec_symbols, provider, oos_end, surface,
                           WF_DIR / f"fold{fold_i}_rows")
        if ds.empty:
            return {"fold": fold_i, "error": "no dataset rows"}
        ds["split"] = fold_splits(ds, train_end, oos_start, oos_end)
        ds = ds[ds["split"] != "purged"].reset_index(drop=True)
        ds.to_parquet(ds_path, index=False)

    if membership:
        # point-in-time universe (v5): a (symbol, month) row survives only if
        # the symbol was a member per the frozen monthlies; applied after the
        # checkpoint so pre-filter checkpoints resume correctly
        from nn_meta.universe_pit import membership_mask
        keep = membership_mask(ds["symbol"], ds["entry_date"])
        print(f"  membership: kept {int(keep.sum())}/{len(ds)} rows", flush=True)
        ds = ds[keep].reset_index(drop=True)
        if ds.empty:
            return {"fold": fold_i, "error": "no rows after membership filter"}

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
    lab_tag = "win" if label_col == "label" else "xs"
    preds = []
    prediction_key = frame_digest(oos_rows)
    training_key = hashlib.sha256((frame_digest(ds) + json.dumps(winning, sort_keys=True)
                                   + CONTRACT_VERSION).encode()).hexdigest()
    for seed in config.SEEDS:
        pred_path = WF_DIR / f"fold{fold_i}_preds_s{seed}.npy"
        pred_meta = pred_path.with_suffix(".json")
        expected_meta = {"rows": prediction_key, "training": training_key, "seed": seed}
        if pred_path.exists() and pred_meta.exists() and json.loads(pred_meta.read_text()) == expected_meta:
            p = np.load(pred_path)
            if len(p) == len(oos_rows):
                preds.append(p)
                print(f"  seed {seed}: checkpointed preds", flush=True)
                continue
        run_id = f"a{winning['arch']}-lr{winning['lr']:g}-{lab_tag}-s{seed}"
        run_meta = config.RUNS_DIR / run_id / "fold_context.json"
        if (reuse_runs and (config.RUNS_DIR / run_id / "model.keras").exists()
                and run_meta.exists() and json.loads(run_meta.read_text()) == expected_meta):
            print(f"  seed {seed}: reusing existing run dir", flush=True)
        else:
            r = run_one(ds, arch, winning["lr"], seed, config.MAX_EPOCHS, label_col)
            run_id = r["run_id"]
            (config.RUNS_DIR / run_id / "fold_context.json").write_text(json.dumps(expected_meta))
            print(f"  seed {seed}: val_loss={r['val_loss']:.4f}", flush=True)
        p = predict_rows(run_id, oos_rows)
        np.save(pred_path, p)
        pred_meta.write_text(json.dumps(expected_meta))
        preds.append(p)

    # 4) OOS: ensemble (winner's mode) vs fold-frozen baseline AND B&H
    ens = np.mean(preds, axis=0)
    nn = _EVALUATORS[mode](oos_rows, ens, winning["threshold"])
    base_pool = rows_all[fmask]
    base = portfolio_metrics(base_pool)
    bh = basket_buy_hold(fold_spec, oos_start, oos_end)
    nn_ret = nn["total_return"] if nn["total_return"] is not None else -np.inf
    beat_base = nn_ret > (base["total_return"] if base["total_return"] is not None else -np.inf)
    beat_bh = nn_ret > bh
    print(f"  OOS: NN {fmt(nn['total_return'])} ({nn['n_kept']}/{nn['n_proposals']} kept, "
          f"ex-top3 {fmt(nn['total_ex_top3'])}) "
          f"vs baseline {fmt(base['total_return'])} ({base['n']}) "
          f"vs B&H {fmt(bh)} "
          f"→ {'beats both' if beat_base and beat_bh else 'beats baseline only' if beat_base else 'beats B&H only' if beat_bh else 'beats neither'}",
          flush=True)
    res = {"fold": fold_i, "train_end": train_end,
           "oos": f"{oos_start}→{oos_end}",
           "n_symbols": len(spec_symbols),
           "nn_return": nn["total_return"], "nn_kept": nn["n_kept"],
           "nn_ex_top3": nn["total_ex_top3"],
           "base_return": base["total_return"], "base_n": base["n"],
           "bh_return": bh,
           "nn_beats": bool(beat_base), "nn_beats_bh": bool(beat_bh),
           "error": None}
    _save_json(WF_DIR / f"fold{fold_i}_result.json", res)
    return res


def main() -> None:
    global WF_DIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--reuse-runs", default="",
                    help="comma-separated fold numbers whose existing runs/ "
                         "model dirs should be reused instead of retrained "
                         "(only for resuming that same fold)")
    ap.add_argument("--membership", action=argparse.BooleanOptionalAction,
                    default=(config.POOL in ("v5", "v6")),
                    help="restrict fold datasets to point-in-time universe "
                         "members per (symbol, month) — default ON for v5")
    args = ap.parse_args()
    reuse_folds = {int(x) for x in args.reuse_runs.split(",") if x.strip()}

    config.ensure_dirs()
    WF_DIR.mkdir(parents=True, exist_ok=True)
    ens_path = config.MODEL_FINAL_DIR / "ensemble_config.json"
    if not ens_path.exists():
        raise SystemExit("run select_meta first — walk-forward retrains the "
                         "winning config only")
    winning = json.loads(ens_path.read_text())
    if winning.get("feature_contract_version") != CONTRACT_VERSION:
        raise SystemExit("walk-forward winner predates causal fixes; rerun training/selection")
    WF_DIR = config.ARTIFACTS / "wf" / experiment_key(winning, args.folds, args.membership)
    WF_DIR.mkdir(parents=True, exist_ok=True)

    provider = get_provider()
    surface = load_surface_features()
    results = []
    for i, b in enumerate(fold_boundaries(args.folds)):
        res_path = WF_DIR / f"fold{i + 1}_result.json"
        if res_path.exists():
            print(f"\n─ fold {i + 1}: complete (checkpointed result)", flush=True)
            results.append(json.loads(res_path.read_text()))
            continue
        results.append(run_fold(i + 1, *b, winning, provider, surface,
                                reuse_runs=(i + 1) in reuse_folds,
                                membership=args.membership))

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
