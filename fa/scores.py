# fa/scores.py — Stage 2: per-source attention/sentiment scores.
"""Velocity, not level: z-score of attention vs each ticker's OWN trailing
``config.BASELINE_DAYS`` baseline (SPY is always trending; a spike for $KODK is
signal).  Output rows ``(ticker, observed_at, source_family, score,
evidence_ref)`` are exactly what ``fa.universe_loop.monthly_rank`` consumes;
evidence links back to raw archive rows so every ranking is auditable.

This wires the raw Stage-0 collector archive through entity resolution into the
normalized score table — the missing bridge between collectors and ranking.
"""
from __future__ import annotations

from typing import Iterable, Mapping

import pandas as pd

from fa import config
from fa.entities import resolve

SCORE_COLUMNS = ["ticker", "observed_at", "source_family", "score", "evidence_ref"]
_MENTION_COLUMNS = ["ticker", "observed_at", "source_family", "evidence_ref"]


def resolve_mentions(raw: pd.DataFrame, aliases: Mapping[str, str], *,
                     source_family: str, text_col: str = "text",
                     ts_col: str = "ts_utc", ref_col: str | None = None,
                     valid_tickers: Iterable[str] | None = None) -> pd.DataFrame:
    """Explode raw archive rows into one resolved (ticker, time) mention per row."""
    rows = []
    for r in raw.itertuples(index=False):
        ts = getattr(r, ts_col)
        ref = getattr(r, ref_col) if ref_col else f"{source_family}:{ts}"
        for ticker in resolve(str(getattr(r, text_col)), aliases,
                              valid_tickers=valid_tickers):
            rows.append({"ticker": ticker, "observed_at": ts,
                         "source_family": source_family, "evidence_ref": ref})
    return pd.DataFrame(rows, columns=_MENTION_COLUMNS)


def attention_velocity(mentions: pd.DataFrame, *,
                       baseline_days: int = config.BASELINE_DAYS,
                       min_baseline: int = 10, std_floor: float = 1.0) -> pd.DataFrame:
    """Per-(ticker, source) daily mention velocity z-scored vs its own baseline.

    The baseline is the trailing ``baseline_days`` of daily counts *strictly
    before* each day (zero-filled on quiet days), so the score is point-in-time
    and rewards a spike over a quiet history.  Days without enough baseline
    history are dropped rather than guessed.
    """
    if mentions.empty:
        return pd.DataFrame(columns=SCORE_COLUMNS)
    m = mentions.copy()
    # Archives mix tz-aware UTC stamps (collectors) with provider-local naive
    # strings; normalize everything to naive UTC once, drop the unparseable.
    m["observed_at"] = pd.to_datetime(m["observed_at"], utc=True,
                                      errors="coerce").dt.tz_localize(None)
    m = m.dropna(subset=["observed_at"])
    m["day"] = m["observed_at"].dt.normalize()
    daily = m.groupby(["ticker", "source_family", "day"], as_index=False).agg(
        count=("evidence_ref", "size"), evidence_ref=("evidence_ref", "first"))

    out = []
    for (ticker, source), g in daily.groupby(["ticker", "source_family"]):
        g = g.sort_values("day")
        full = pd.date_range(g["day"].min(), g["day"].max(), freq="D")
        counts = g.set_index("day")["count"].reindex(full, fill_value=0)
        prior = counts.shift(1)
        roll_mean = prior.rolling(baseline_days, min_periods=min_baseline).mean()
        roll_std = prior.rolling(baseline_days, min_periods=min_baseline).std()
        for day, ref in zip(g["day"], g["evidence_ref"]):
            mean = roll_mean.get(day)
            if pd.isna(mean):                       # insufficient baseline history
                continue
            std = roll_std.get(day)
            std = std_floor if pd.isna(std) else max(float(std), std_floor)
            out.append({"ticker": ticker, "observed_at": day, "source_family": source,
                        "score": float((counts[day] - mean) / std), "evidence_ref": ref})
    return pd.DataFrame(out, columns=SCORE_COLUMNS)


def build_score_table(sources: Iterable[tuple], aliases: Mapping[str, str], *,
                      baseline_days: int = config.BASELINE_DAYS,
                      min_baseline: int = 10,
                      valid_tickers: Iterable[str] | None = None) -> pd.DataFrame:
    """Raw collector archives → resolved mentions → normalized score table.

    ``sources`` is an iterable of ``(source_family, raw_df, colmap)`` where
    ``colmap`` names the text/ts/ref columns.  The result feeds
    ``fa.universe_loop.monthly_rank`` directly.
    """
    frames = []
    for source_family, raw, colmap in sources:
        frames.append(resolve_mentions(raw, aliases, source_family=source_family,
                                        valid_tickers=valid_tickers, **colmap))
    mentions = (pd.concat(frames, ignore_index=True) if frames
                else pd.DataFrame(columns=_MENTION_COLUMNS))
    return attention_velocity(mentions, baseline_days=baseline_days,
                              min_baseline=min_baseline)
