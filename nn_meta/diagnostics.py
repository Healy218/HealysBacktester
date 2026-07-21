"""Score-decile diagnostics for the v4 meta-classifier.

v3.1 calibration showed win rate rising cleanly with model score while mean
return *inverted* at the top decile: the model predicts win probability, not
win size, so its most confident trades win often but win small.  This table is
emitted in every v4 report so the inversion is tracked continuously rather than
rediscovered.  See the magnitude-aware label backlog item in V4_OUTLINE.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def score_decile_table(scores, returns, *, n_bins: int = 10) -> pd.DataFrame:
    """Per score-decile count, mean score, win rate, and mean return.

    Deciles are ranked so ties do not collapse a bin.  ``n_bins`` is reduced
    when there are too few distinct scores or rows to fill it.
    """
    df = pd.DataFrame({"score": np.asarray(scores, dtype=float),
                       "ret": np.asarray(returns, dtype=float)}).dropna()
    bins = min(n_bins, df["score"].nunique(), len(df))
    if bins < 2:
        return pd.DataFrame(columns=["decile", "n", "mean_score", "win_rate",
                                     "mean_return"])
    df["decile"] = pd.qcut(df["score"].rank(method="first"), bins,
                           labels=range(1, bins + 1))
    out = df.groupby("decile", observed=True).agg(
        n=("ret", "size"), mean_score=("score", "mean"),
        win_rate=("ret", lambda s: float((s > 0).mean())),
        mean_return=("ret", "mean"),
    ).reset_index()
    return out


def top_decile_inverted(table: pd.DataFrame) -> bool:
    """True when the highest-score decile's mean return is below the median decile.

    This is the v3.1 pathology: confident trades that win often but small.
    """
    if len(table) < 2:
        return False
    ordered = table.sort_values("mean_score")
    return bool(ordered["mean_return"].iloc[-1] < ordered["mean_return"].median())


def decile_diagnostic(scores, returns, *, n_bins: int = 10) -> dict | None:
    """Report-ready decile table plus the inversion flag, or None if too sparse."""
    table = score_decile_table(scores, returns, n_bins=n_bins)
    if table.empty:
        return None
    return {"inverted": top_decile_inverted(table),
            "deciles": table.round(4).to_dict("records")}
