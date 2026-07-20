"""Point-in-time FA ranking and graduation helpers.

These functions operate only on archived, timestamped score rows.  They do
not fetch data and cannot silently promote a name using information observed
after the ranking date.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


class UniverseLoopError(ValueError):
    pass


def monthly_rank(scores: pd.DataFrame, *, as_of: str | pd.Timestamp,
                 top_n: int = 10, min_source_families: int = 2) -> pd.DataFrame:
    """Freeze a point-in-time, corroborated ranking from normalized scores."""
    required = {"ticker", "observed_at", "source_family", "score", "evidence_ref"}
    missing = required - set(scores.columns)
    if missing:
        raise UniverseLoopError(f"missing score fields: {sorted(missing)}")
    cutoff = pd.Timestamp(as_of)
    rows = scores.copy()
    rows["observed_at"] = pd.to_datetime(rows["observed_at"])
    rows = rows[rows["observed_at"] <= cutoff]
    if rows.empty:
        return pd.DataFrame(columns=["ticker", "score", "source_families", "evidence_refs"])
    grouped = rows.groupby("ticker", as_index=False).agg(
        score=("score", "mean"), source_families=("source_family", "nunique"),
        evidence_refs=("evidence_ref", lambda s: sorted(set(map(str, s)))),
    )
    return grouped[grouped["source_families"] >= min_source_families] \
        .sort_values(["score", "ticker"], ascending=[False, True]).head(top_n).reset_index(drop=True)


def freeze_ranking(path: Path, ranking: pd.DataFrame, *, as_of: str | pd.Timestamp) -> Path:
    """Write once: a dated ranking may not be overwritten retroactively."""
    path = Path(path)
    if path.exists():
        raise UniverseLoopError(f"ranking already frozen: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"as_of": pd.Timestamp(as_of).isoformat(),
               "rows": ranking.to_dict(orient="records")}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def eligible_graduates(rankings: pd.DataFrame, forward_returns: pd.DataFrame, *,
                       as_of: str | pd.Timestamp, probation_days: int = 90,
                       min_excess_return: float = 0.0) -> pd.DataFrame:
    """Return names eligible on the date, never based on future observations."""
    required_rank = {"ticker", "ranking_date"}
    required_ret = {"ticker", "as_of", "excess_return"}
    if missing := required_rank - set(rankings.columns):
        raise UniverseLoopError(f"missing ranking fields: {sorted(missing)}")
    if missing := required_ret - set(forward_returns.columns):
        raise UniverseLoopError(f"missing return fields: {sorted(missing)}")
    cutoff = pd.Timestamp(as_of)
    ranks, rets = rankings.copy(), forward_returns.copy()
    ranks["ranking_date"] = pd.to_datetime(ranks["ranking_date"])
    rets["as_of"] = pd.to_datetime(rets["as_of"])
    eligible = ranks[ranks["ranking_date"] + pd.Timedelta(days=probation_days) <= cutoff]
    rets = rets[rets["as_of"] <= cutoff]
    latest = rets.sort_values("as_of").groupby("ticker", as_index=False).tail(1)
    return eligible.merge(latest, on="ticker", how="inner").query(
        "excess_return >= @min_excess_return"
    ).sort_values("ticker").reset_index(drop=True)
