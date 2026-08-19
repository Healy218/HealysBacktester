"""The 2026-08-19 gap must never pass silently again."""
import pandas as pd
import pytest

from nn_meta.cache_preflight import check


def _cache(tmp_path, days, trading):
    (tmp_path / "flatfiles_15m").mkdir()
    for d in days:
        (tmp_path / "flatfiles_15m" / f"{d}.parquet").touch()
    pd.DataFrame({
        "timestamp": pd.to_datetime([f"{d} 14:30" for d in trading]),
        "symbol": ["SPY"] * len(trading),
    }).to_parquet(tmp_path / "underlying_15m.parquet")
    return tmp_path


TRADING = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08", "2026-01-09"]


def test_complete_cache_passes(tmp_path):
    ok, missing, stats = check(_cache(tmp_path, TRADING, TRADING))
    assert ok and missing == []
    assert stats["missing"] == 0


def test_interior_hole_is_fatal(tmp_path):
    """The real failure mode: a day inside the archive span never uploaded."""
    have = [d for d in TRADING if d != "2026-01-07"]
    ok, missing, _ = check(_cache(tmp_path, have, TRADING))
    assert not ok
    assert missing == ["2026-01-07"]


def test_window_is_scoped_to_the_archive(tmp_path):
    """The underlying archive reaches back years before the flat files; days
    outside the day-frame span must not be reported as holes."""
    have = TRADING[1:4]
    ok, missing, stats = check(_cache(tmp_path, have, ["2017-03-27"] + TRADING))
    assert ok, missing
    assert stats["window"] == "2026-01-06 .. 2026-01-08"


def test_explicit_window_catches_an_edge_hole(tmp_path):
    """Documented limit of the default window — pinning start/end removes it."""
    have = TRADING[1:]                      # 2026-01-05 missing at the edge
    c = _cache(tmp_path, have, TRADING)
    ok, _, _ = check(c)                     # default window hides it
    assert ok
    ok, missing, _ = check(c, start="2026-01-05", end="2026-01-09")
    assert not ok and missing == ["2026-01-05"]


def test_empty_cache_is_fatal(tmp_path):
    ok, _, stats = check(_cache(tmp_path, [], TRADING))
    assert not ok
    assert stats["flatfile_days"] == 0
