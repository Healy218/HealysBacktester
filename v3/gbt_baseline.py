# v3/gbt_baseline.py — the boring baseline the standing rule demands.
"""LightGBM on the SAME meta dataset / features / label / splits as the NN
ensemble. Answers two questions before the big at-scale run:

  1. Does the 40-model NN actually beat a gradient-boosted tree? (val/test AUC)
  2. Which features and which STRATEGIES earn their place? (gain importance)

Trees handle NaNs and unscaled features natively, so this is a genuinely
independent modeling path — not a reimplementation of the NN. Run under the
same pool as the dataset you want to judge:

    NN_META_POOL=v3 python -m v3.gbt_baseline [--label label_excess]

Writes v3/artifacts/gbt_report.md.
"""
import argparse

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, early_stopping, log_evaluation
from sklearn.metrics import roc_auc_score

from nn_meta import config
from nn_meta.build_meta_dataset import META_FEATURES


def _xy(ds: pd.DataFrame, split: str, label: str):
    m = (ds["split"] == split) & ds[label].notna()
    sub = ds[m]
    return sub[META_FEATURES], sub[label].astype(int)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="label_excess",
                    help="label_excess (v3 winner) or label")
    args = ap.parse_args()

    ds = pd.read_parquet(config.ARTIFACTS / "meta_dataset.parquet")
    Xtr, ytr = _xy(ds, "train", args.label)
    Xva, yva = _xy(ds, "val", args.label)
    Xte, yte = _xy(ds, "test", args.label)
    print(f"pool={config.POOL} label={args.label} | "
          f"train {len(Xtr):,} / val {len(Xva):,} / test {len(Xte):,}")

    clf = LGBMClassifier(
        n_estimators=2000, learning_rate=0.02, num_leaves=31,
        subsample=0.8, colsample_bytree=0.8, min_child_samples=200,
        reg_lambda=1.0, random_state=0, n_jobs=-1, verbosity=-1)
    clf.fit(Xtr, ytr, eval_set=[(Xva, yva)], eval_metric="auc",
            callbacks=[early_stopping(100), log_evaluation(0)])

    auc = {s: roc_auc_score(y, clf.predict_proba(X)[:, 1])
           for s, (X, y) in (("train", (Xtr, ytr)), ("val", (Xva, yva)),
                             ("test", (Xte, yte)))}
    print(f"AUC  train {auc['train']:.3f} | val {auc['val']:.3f} | "
          f"test {auc['test']:.3f}   (NN v3 val≈0.62)")

    imp = (pd.Series(clf.booster_.feature_importance("gain"),
                     index=META_FEATURES).sort_values(ascending=False))
    imp_pct = 100 * imp / imp.sum()

    # collapse strategy one-hots into a per-strategy share
    strat_share = {s: imp_pct.get(f"strat_{s}", 0.0)
                   for s in config.PROPOSAL_STRATEGIES}

    lines = ["# v3 GBT baseline (LightGBM) vs the NN ensemble", "",
             f"Pool **{config.POOL}**, label **{args.label}**, "
             f"{clf.best_iteration_} trees (early-stopped).", "",
             "| model | val AUC | test AUC |", "|---|---|---|",
             f"| LightGBM | {auc['val']:.3f} | {auc['test']:.3f} |",
             "| NN 40-seed ensemble | ~0.62 | (see meta_report) |", "",
             "## Top 20 features by gain", "",
             "| feature | gain % |", "|---|---|"]
    lines += [f"| {k} | {v:.1f} |" for k, v in imp_pct.head(20).items()]
    lines += ["", "## Strategy one-hot importance (does each earn its seat?)",
              "", "| strategy | gain % |", "|---|---|"]
    lines += [f"| {k} | {v:.2f} |"
              for k, v in sorted(strat_share.items(),
                                 key=lambda kv: -kv[1])]

    config.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    out = config.ARTIFACTS / "gbt_report.md"
    out.write_text("\n".join(lines))
    print("\n".join(lines[3:]))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
