# v3/models.py — Stages 7–8: model bake-off + walk-forward with regime report.
"""LightGBM baseline first (feature importances rank the new indicators),
NN ensemble second, sequence model only if tabular plateaus. Winner = best
out-of-fold portfolio metrics with costs, ex-outliers — never val loss.

Walk-forward: purged/embargoed folds PLUS per-regime slices (2018 volmageddon,
2020 crash, 2021 meme, 2022 bear, 2023-25). 'Only works post-2021' is a
finding, not a failure."""
