"""FA stage 4+5: composite ranking (corroboration, liquidity floor,
point-in-time freeze) and forward-return tracking. Synthetic archives only."""
import json

import numpy as np
import pandas as pd
import pytest

from fa import config
from fa.ranker import build_monthly_ranking, load_mention_sources, render_md
from fa.tracker import forward_returns, load_frozen_rankings
from fa.universe_loop import UniverseLoopError, freeze_ranking

AS_OF = pd.Timestamp("2026-08-24")


def _archive(tmp_path, *, days=40, social_sym="AAPL", news_sym="AAPL",
             spike_day="2026-08-20"):
    """A tiny archive: quiet daily mentions with one spike day, in reddit
    (social) and news; a social-only name TSLA; junk $LOL and crypto ETH.X."""
    arch = tmp_path / "archive"
    dates = pd.date_range(end=AS_OF, periods=days, freq="D")
    reddit = []
    for i, d in enumerate(dates):
        n = 8 if str(d.date()) == spike_day else 1
        for k in range(n):
            reddit.append({"title": f"${social_sym} to the moon $TSLA $LOL",
                           "selftext": "", "post_id": f"p{i}-{k}",
                           "created_utc": d, "ts_utc": d})
    (arch / "reddit").mkdir(parents=True)
    pd.DataFrame(reddit).to_parquet(arch / "reddit" / "2026-08.parquet")
    news = []
    for i, d in enumerate(dates):
        n = 6 if str(d.date()) == spike_day else 1
        for k in range(n):
            news.append({"tickers": news_sym, "published": d, "ts_utc": d,
                         "provider": "finnhub", "url": f"u{i}-{k}"})
    (arch / "news").mkdir(parents=True)
    pd.DataFrame(news).to_parquet(arch / "news" / "2026-08.parquet")
    st = [{"symbol": "ETH.X", "ts_utc": d} for d in dates]
    (arch / "stocktwits").mkdir(parents=True)
    pd.DataFrame(st).to_parquet(arch / "stocktwits" / "2026-08.parquet")
    return arch


def test_ranking_requires_corroboration_and_liquidity(tmp_path):
    arch = _archive(tmp_path)
    ranking, meta = build_monthly_ranking(AS_OF, archive=arch)
    # AAPL: social + news spike -> ranked. TSLA: social only -> gated.
    # $LOL: not a liquid ticker -> never resolved. ETH.X: outside universe.
    assert list(ranking["ticker"]) == ["AAPL"]
    assert ranking.iloc[0]["source_families"] == 2
    assert bool(ranking.iloc[0]["new"]) in (True, False)   # flag present
    assert meta["tickers_scored"] >= 1
    md = render_md(ranking, meta)
    assert "AAPL" in md and "families" in md


def test_ranking_is_point_in_time(tmp_path):
    arch = _archive(tmp_path, spike_day="2026-08-20")
    before, _ = build_monthly_ranking(pd.Timestamp("2026-08-19"), archive=arch)
    # the spike hasn't happened yet at the earlier cutoff
    assert before.empty or before.iloc[0]["score"] < 3


def test_source_families_pool_social(tmp_path):
    arch = _archive(tmp_path)
    fams = {f for f, _, _ in load_mention_sources(arch)}
    assert fams == {"social", "news"}


def test_freeze_is_write_once(tmp_path):
    r = pd.DataFrame([{"ticker": "AAPL", "score": 1.0, "source_families": 2,
                       "evidence_refs": ["x"], "new": False}])
    p = tmp_path / "top10_2026-08.json"
    freeze_ranking(p, r, as_of=AS_OF)
    with pytest.raises(UniverseLoopError, match="already frozen"):
        freeze_ranking(p, r, as_of=AS_OF)
    loaded = load_frozen_rankings(tmp_path)
    assert list(loaded["ticker"]) == ["AAPL"]
    assert loaded.iloc[0]["ranking_date"] == AS_OF.normalize()


def test_forward_returns_windows_and_excess():
    ranks = pd.DataFrame([
        {"ticker": "AAPL", "ranking_date": pd.Timestamp("2026-08-01")},
        {"ticker": "NOBARS", "ranking_date": pd.Timestamp("2026-08-01")},
        {"ticker": "TOOSOON", "ranking_date": pd.Timestamp("2026-09-01")},
    ])
    idx = pd.date_range("2026-08-01", "2026-08-24", freq="D")
    series = {"AAPL": pd.Series(np.linspace(100, 110, len(idx)), index=idx),
              "SPY": pd.Series(np.linspace(100, 105, len(idx)), index=idx)}
    rets = forward_returns(ranks, lambda t: series.get(t),
                           as_of="2026-08-24", baseline=["SPY"])
    assert list(rets["ticker"]) == ["AAPL"]        # no bars / too soon dropped
    r = rets.iloc[0]
    assert r["fwd_return"] == pytest.approx(0.10)
    assert r["baseline_return"] == pytest.approx(0.05)
    assert r["excess_return"] == pytest.approx(0.05)
