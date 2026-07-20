import pandas as pd
import pytest

from fa.universe_loop import (UniverseLoopError, eligible_graduates, freeze_ranking,
                              monthly_rank)


def test_ranking_is_point_in_time_and_requires_corroboration(tmp_path):
    scores = pd.DataFrame([
        ("AAA", "2025-01-01", "social", 4.0, "a"),
        ("AAA", "2025-01-01", "news", 2.0, "b"),
        ("BBB", "2025-01-01", "social", 9.0, "c"),
        ("CCC", "2025-02-01", "social", 99.0, "d"),
        ("CCC", "2025-02-01", "news", 99.0, "e"),
    ], columns=["ticker", "observed_at", "source_family", "score", "evidence_ref"])
    ranked = monthly_rank(scores, as_of="2025-01-31")
    assert ranked["ticker"].tolist() == ["AAA"]
    path = freeze_ranking(tmp_path / "2025-01.json", ranked, as_of="2025-01-31")
    with pytest.raises(UniverseLoopError, match="already frozen"):
        freeze_ranking(path, ranked, as_of="2025-01-31")


def test_graduation_never_uses_future_return():
    ranks = pd.DataFrame({"ticker": ["AAA"], "ranking_date": ["2025-01-01"]})
    returns = pd.DataFrame({"ticker": ["AAA", "AAA"],
                            "as_of": ["2025-03-31", "2025-05-01"],
                            "excess_return": [0.1, -0.2]})
    assert eligible_graduates(ranks, returns, as_of="2025-04-01", probation_days=90)["ticker"].tolist() == ["AAA"]
    assert eligible_graduates(ranks, returns, as_of="2025-05-02", probation_days=90).empty
