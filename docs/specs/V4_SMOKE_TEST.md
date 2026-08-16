# V4 Smoke Test — run this before the full ablation

Instructions for whoever picks this up next (MacBook session). Read
`V4_OUTLINE.md` first for the full context; this file is just the "test on
10 symbols over a year before trying it on the real thing" step, the way the
original v1 backtest started small before scaling up.

## Why

`nn_meta/v4_evaluate.py`'s nested per-fold model/threshold selection has
never been run against real data — it's been blocked on the v31 dataset
until 2026-07-21. The `--smoke` flag only shrinks the model fit (1 seed, 5
epochs, 50 GBT trees instead of 5/60/600) — it still loads and processes the
full 489k-row, 118-symbol `meta_dataset.parquet`. It does **not** test
whether the pipeline itself (purging, feature contract, empty-split
handling, GBT/TF plumbing) runs cleanly. A 10-symbol/~1-year subset does
that in under a minute instead of after a multi-hour full run.

## You do NOT need anything from the Windows/WSL box beyond `git pull`

This is worth stating plainly because it's easy to assume otherwise: the
120-symbol universe's raw option-bar cache (`nn_meta/data_cache_v3/`, 5.6GB,
Windows/WSL-only) is **not** read anywhere in `v4_evaluate.py`,
`v4_preflight.py`, `feature_contract.py`, or `temporal_validation.py` —
confirmed by reading all four files. They only ever touch the already-
assembled `nn_meta/artifacts_v31/meta_dataset.parquet` (35MB) and
`baseline_spec.json` (1.4MB), both committed to `main` as of commit
`65c635c`. Once you've pulled `main` and merged/rebased
`codex/v4-causal-validation` on top of it, you have everything needed —
including for the full-scale run later, not just this smoke test.

## Steps

1. On the MacBook: `git fetch origin && git checkout codex/v4-causal-validation
   && git merge origin/main` (should be conflict-free — the v4 branch and
   main's new commit only touch disjoint files).
2. Build the subset. Deliberately include **TQQQ** — it's the single trade
   that drove v3.1's walk-forward fold 2's fragile +1136% result almost by
   itself (a 31x overnight return, 10 DTE, entered 2025-11-19). Worth seeing
   whether v4's purging/schema treats it any differently.

   ```python
   import pandas as pd
   from nn_meta import config  # run with NN_META_POOL=v31

   ds = pd.read_parquet(config.META_DATASET_PARQUET)
   symbols = ["TQQQ", "AAPL", "MSFT", "NVDA", "SPY",
              "AMD", "COIN", "TSLA", "XLE", "JPM"]  # 10 symbols, adjust freely
   sub = ds[ds["symbol"].isin(symbols)].copy()
   entry = pd.to_datetime(sub["entry_ts"])
   cutoff = entry.max() - pd.Timedelta(days=365)
   sub = sub[entry >= cutoff]
   out = config.ARTIFACTS / "smoke_subset.parquet"
   sub.to_parquet(out, index=False)
   print(f"{len(sub)} rows, {sub['symbol'].nunique()} symbols -> {out}")
   ```

3. Preflight against the subset:
   ```
   NN_META_POOL=v31 python -m nn_meta.v4_preflight --require-gbt \
     --dataset nn_meta/artifacts_v31/smoke_subset.parquet
   ```
4. Run both evaluation modes against the subset:
   ```
   NN_META_POOL=v31 python -m nn_meta.v4_evaluate --ablation --smoke \
     --dataset nn_meta/artifacts_v31/smoke_subset.parquet
   NN_META_POOL=v31 python -m nn_meta.v4_evaluate --folds 1 --smoke \
     --dataset nn_meta/artifacts_v31/smoke_subset.parquet
   ```

## Pass / fail

This is a plumbing check, not a performance check — do not judge the
strategy on these numbers, the sample is tiny and cherry-picked (TQQQ
included on purpose).

**Pass**: both commands complete without exceptions; `v4_ablation_report.md`
/ `v4_walkforward_report.md` show real (non-`n/a`) test returns and maxDD for
each of the 4 ablation rows / the 1 fold; the manifest JSON writes
successfully.

**Fail** (fix before running the real thing): any traceback, an empty
train/val/test partition error (subset window/symbol choice may need
adjusting — widen the date range or swap in a more active symbol), or a
`v4_feature_contract` / `dataset_feature_schema` preflight failure (a real
bug worth chasing before it burns hours on the full dataset).

## After it passes

Proceed to the real run — on whichever machine is more convenient, since
neither needs anything beyond what's already in `main`:
```
NN_META_POOL=v31 python -m nn_meta.v4_evaluate --ablation \
  --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D
NN_META_POOL=v31 python -m nn_meta.v4_evaluate \
  --folds 3 --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600 --embargo 1D
```
Expect this to take comparably long or longer than the original v3.1
walk-forward (multi-hour) — nested per-fold selection re-picks
architecture/threshold inside every fold rather than reusing one fixed
config, which is more compute, not less.
