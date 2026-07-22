"""FA score-table bridge: entity resolution + attention velocity → ranking."""
import pandas as pd
import pytest

from fa.entities import resolve
from fa.scores import (attention_velocity, build_score_table, resolve_mentions)
from fa.universe_loop import monthly_rank

ALIASES = {"tesla": "TSLA", "elon": "TSLA"}


def test_resolve_cashtags_aliases_and_precision():
    assert resolve("$TSLA and tesla ripping, elon tweeting", ALIASES) == ["TSLA"]
    assert resolve("no tickers here", ALIASES) == []
    # valid_tickers drops cashtag noise like $LOL.
    assert resolve("$LOL $TSLA", ALIASES, valid_tickers={"TSLA"}) == ["TSLA"]


def test_resolve_mentions_explodes_rows():
    raw = pd.DataFrame({"text": ["$AAPL $MSFT", "nothing"],
                        "ts_utc": pd.to_datetime(["2026-01-01", "2026-01-01"])})
    mentions = resolve_mentions(raw, {}, source_family="reddit")
    assert sorted(mentions["ticker"]) == ["AAPL", "MSFT"]
    assert set(mentions["source_family"]) == {"reddit"}


def _daily_mentions(ticker, source, counts, start="2026-01-01"):
    base = pd.Timestamp(start)
    rows = []
    for offset, count in enumerate(counts):
        for _ in range(count):
            rows.append({"ticker": ticker, "source_family": source,
                         "observed_at": base + pd.Timedelta(days=offset),
                         "evidence_ref": f"{source}:{offset}"})
    return pd.DataFrame(rows)


def test_attention_velocity_flags_a_spike_over_quiet_baseline():
    mentions = _daily_mentions("KODK", "reddit", [1, 1, 1, 1, 1, 1, 1, 8])
    scores = attention_velocity(mentions, baseline_days=5, min_baseline=3)
    assert not scores.empty
    spike = scores.sort_values("observed_at").iloc[-1]
    assert spike["observed_at"] == pd.Timestamp("2026-01-08")
    assert spike["score"] > 3.0                       # a real velocity spike
    # Early days without enough baseline history are dropped, not guessed.
    assert scores["observed_at"].min() >= pd.Timestamp("2026-01-04")


def _raw(ticker, counts, start="2026-01-01"):
    base = pd.Timestamp(start)
    rows = []
    for offset, count in enumerate(counts):
        for _ in range(count):
            rows.append({"text": f"${ticker} to the moon",
                         "ts_utc": base + pd.Timedelta(days=offset)})
    return pd.DataFrame(rows)


def test_build_score_table_feeds_corroborated_ranking():
    spike = [1, 1, 1, 1, 1, 1, 1, 8]
    reddit = pd.concat([_raw("KODK", spike), _raw("SOLO", spike)], ignore_index=True)
    stocktwits = _raw("KODK", spike)                  # SOLO only in one family
    cols = {"text_col": "text", "ts_col": "ts_utc"}
    table = build_score_table(
        [("reddit", reddit, cols), ("stocktwits", stocktwits, cols)],
        aliases={}, baseline_days=5, min_baseline=3,
        valid_tickers={"KODK", "SOLO"})
    assert set(table.columns) == {"ticker", "observed_at", "source_family",
                                  "score", "evidence_ref"}
    ranking = monthly_rank(table, as_of="2026-01-08", min_source_families=2)
    # KODK is corroborated by two source families; SOLO (one family) is excluded.
    assert "KODK" in set(ranking["ticker"])
    assert "SOLO" not in set(ranking["ticker"])


def test_empty_inputs_are_safe():
    assert build_score_table([], aliases={}).empty
    assert attention_velocity(pd.DataFrame(columns=["ticker", "observed_at",
                                                    "source_family", "evidence_ref"])).empty
