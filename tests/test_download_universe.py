"""Universe filter: the frozen research window vs the live-horizon refresh.

The 2026-08-16 production find: the deployed scanner's chain ends at
WINDOW_END + DTE_MAX because the universe filter clips every contract's
entry-eligible span to the frozen research window — so the live chain
silently empties when that horizon passes. ``--live-horizon`` rebuilds the
universe through today+N without touching the frozen window constants.
"""
import pandas as pd

from nn_meta import config
from nn_meta.download_universe import _universe_for


def _closes():
    return pd.Series(100.0, index=pd.bdate_range("2026-05-01", "2026-08-14"))


def test_frozen_window_drops_post_horizon_expiries():
    beyond = (pd.Timestamp(config.WINDOW_END)
              + pd.Timedelta(days=config.DTE_MAX + 30))
    contracts = pd.DataFrame({"expiration": [beyond], "strike": [100.0]})
    assert not _universe_for(contracts, _closes()).iloc[0]


def test_live_horizon_keeps_future_expiries_at_current_moneyness():
    beyond = (pd.Timestamp(config.WINDOW_END)
              + pd.Timedelta(days=config.DTE_MAX + 30))
    contracts = pd.DataFrame({"expiration": [beyond, beyond],
                              "strike": [100.0, 500.0]})
    keep = _universe_for(contracts, _closes(),
                         win_end=str((beyond + pd.Timedelta(days=30)).date()))
    assert keep.iloc[0]          # ATM strike vs the latest closes → kept
    assert not keep.iloc[1]      # far-OTM strike still filtered by the band


def test_default_behavior_unchanged_inside_the_window():
    inside = pd.Timestamp(config.WINDOW_END) - pd.Timedelta(days=10)
    contracts = pd.DataFrame({"expiration": [inside], "strike": [100.0]})
    closes = pd.Series(100.0, index=pd.bdate_range("2026-04-01", "2026-06-30"))
    assert _universe_for(contracts, closes).iloc[0]


# ── incremental bars refresh (surface freshness, added 2026-08-16) ───────────

def test_prune_manifest_refetches_only_recent_life_contracts(tmp_path, monkeypatch):
    from nn_meta import download_universe as du
    manifest = tmp_path / "bars_done.txt"
    manifest.write_text("OLD1\nRECENT1\nOLD2\nFUTURE1\n")
    monkeypatch.setattr(config, "DONE_MANIFEST", manifest)
    today = pd.Timestamp.today().normalize()
    uni = pd.DataFrame({
        "ticker": ["OLD1", "RECENT1", "OLD2", "FUTURE1", "NEVERFETCHED"],
        "life_end": [(today - pd.Timedelta(days=400)).strftime("%Y-%m-%d"),
                     (today - pd.Timedelta(days=3)).strftime("%Y-%m-%d"),
                     (today - pd.Timedelta(days=100)).strftime("%Y-%m-%d"),
                     (today + pd.Timedelta(days=30)).strftime("%Y-%m-%d"),
                     (today + pd.Timedelta(days=10)).strftime("%Y-%m-%d")]})
    pruned = du.prune_manifest_for_refresh(uni, days=10)
    kept = manifest.read_text().split()
    assert pruned == 2                      # RECENT1 + FUTURE1 refetch
    assert kept == ["OLD1", "OLD2"]         # expired long ago -> stay cached


def test_bootstrap_manifest_from_parts(tmp_path, monkeypatch):
    from nn_meta import download_universe as du
    bars_dir = tmp_path / "bars_daily"
    bars_dir.mkdir()
    pd.DataFrame({"ticker": ["A", "B", "A"], "close": [1.0, 2.0, 3.0]}) \
        .to_parquet(bars_dir / "bars_part_0000.parquet", index=False)
    manifest = tmp_path / "bars_done.txt"
    monkeypatch.setattr(config, "BARS_DAILY_DIR", bars_dir)
    monkeypatch.setattr(config, "DONE_MANIFEST", manifest)
    assert du.bootstrap_manifest_from_parts() == 2
    assert sorted(manifest.read_text().split()) == ["A", "B"]
    # idempotent: an existing manifest is never rebuilt/overwritten
    assert du.bootstrap_manifest_from_parts() == 0


def test_universe_shrink_guard_refuses_drastic_shrink(tmp_path, monkeypatch):
    from nn_meta import download_universe as du
    import pytest as _pytest
    old = tmp_path / "universe.parquet"
    pd.DataFrame({"ticker": [f"T{i}" for i in range(100)]}).to_parquet(old, index=False)
    monkeypatch.setattr(config, "UNIVERSE_PARQUET", old)
    with _pytest.raises(SystemExit, match="shrink guard"):
        du._guard_universe_shrink(pd.DataFrame({"ticker": ["A"] * 10}))
    # 90% of old passes; missing old file passes
    du._guard_universe_shrink(pd.DataFrame({"ticker": ["A"] * 90}))
    monkeypatch.setattr(config, "UNIVERSE_PARQUET", tmp_path / "absent.parquet")
    du._guard_universe_shrink(pd.DataFrame({"ticker": ["A"]}))


# ── bars_daily compaction (unbounded refresh growth, added 2026-08-16) ───────

def _bars_part(bars_dir, name, tickers, closes):
    pd.DataFrame({"ticker": pd.Series(tickers, dtype=object),
                  "date": pd.to_datetime(["2026-06-01"] * len(tickers)),
                  "open": pd.Series([1.0] * len(tickers)),
                  "high": pd.Series([1.0] * len(tickers)),
                  "low": pd.Series([1.0] * len(tickers)),
                  "close": pd.Series(closes, dtype=float),
                  "volume": pd.Series([10] * len(tickers)),
                  "vwap": pd.Series([None] * len(tickers)),
                  "transactions": pd.Series([None] * len(tickers))}) \
        .to_parquet(bars_dir / name, index=False)


def _read_all(bars_dir):
    parts = sorted(bars_dir.glob("bars_part_*.parquet"))
    return pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)


def test_compact_bars_daily_newest_wins_and_swap_is_clean(tmp_path, monkeypatch):
    from nn_meta import download_universe as du
    bars_dir = tmp_path / "bars_daily"
    bars_dir.mkdir()
    _bars_part(bars_dir, "bars_part_0000.parquet", ["A", "B"], [1.0, 2.0])
    _bars_part(bars_dir, "bars_part_0001.parquet", [], [])          # empty part
    _bars_part(bars_dir, "bars_part_0002.parquet", ["A", "C"], [9.0, 3.0])
    monkeypatch.setattr(config, "BARS_DAILY_DIR", bars_dir)
    du.compact_bars_daily()
    out = _read_all(bars_dir)
    # overlap: single A copy survives, from the NEWEST part
    assert out[out["ticker"] == "A"]["close"].tolist() == [9.0]
    # non-overlapping tickers all survive
    assert sorted(out["ticker"]) == ["A", "B", "C"]
    # crash-swap dirs are gone, new dir is dense-renumbered from 0000
    assert not (tmp_path / "bars_daily.old").exists()
    assert not (tmp_path / "bars_daily.compacting").exists()
    assert [p.name for p in sorted(bars_dir.glob("*.parquet"))] == \
        ["bars_part_0000.parquet", "bars_part_0001.parquet"]
    # no ticker spans two parts (newest-processed part carries A+C)
    assert sorted(pd.read_parquet(bars_dir / "bars_part_0000.parquet")["ticker"]) \
        == ["A", "C"]


def test_compact_bars_daily_non_overlapping_parts_untouched(tmp_path, monkeypatch):
    from nn_meta import download_universe as du
    bars_dir = tmp_path / "bars_daily"
    bars_dir.mkdir()
    _bars_part(bars_dir, "bars_part_0000.parquet", ["A"], [1.0])
    _bars_part(bars_dir, "bars_part_0001.parquet", ["B", "C"], [2.0, 3.0])
    monkeypatch.setattr(config, "BARS_DAILY_DIR", bars_dir)
    du.compact_bars_daily()
    out = _read_all(bars_dir)
    assert sorted(zip(out["ticker"], out["close"])) == \
        [("A", 1.0), ("B", 2.0), ("C", 3.0)]


def test_compact_bars_daily_is_idempotent(tmp_path, monkeypatch):
    from nn_meta import download_universe as du
    bars_dir = tmp_path / "bars_daily"
    bars_dir.mkdir()
    _bars_part(bars_dir, "bars_part_0000.parquet", ["A", "B"], [1.0, 2.0])
    _bars_part(bars_dir, "bars_part_0001.parquet", ["A"], [9.0])
    monkeypatch.setattr(config, "BARS_DAILY_DIR", bars_dir)
    du.compact_bars_daily()
    first = _read_all(bars_dir).sort_values("ticker").reset_index(drop=True)
    du.compact_bars_daily()
    second = _read_all(bars_dir).sort_values("ticker").reset_index(drop=True)
    pd.testing.assert_frame_equal(first, second)
    assert sorted(zip(second["ticker"], second["close"])) == \
        [("A", 9.0), ("B", 2.0)]


def test_compact_bars_daily_orders_parts_numerically_not_lexically(
        tmp_path, monkeypatch):
    """The real v31 cache mixes the flat-file pipeline's unpadded parts
    (bars_part_0..12) with the refresh's padded ones (bars_part_0013..);
    lexically bars_part_9 > bars_part_0013, so lexical newest-first would
    keep the STALE flat-file copy and silently drop the refreshed bars."""
    from nn_meta import download_universe as du
    bars_dir = tmp_path / "bars_daily"
    bars_dir.mkdir()
    _bars_part(bars_dir, "bars_part_9.parquet", ["A"], [1.0])       # stale fetch
    _bars_part(bars_dir, "bars_part_0013.parquet", ["A", "A"], [9.0, 9.5])
    monkeypatch.setattr(config, "BARS_DAILY_DIR", bars_dir)
    du.compact_bars_daily()
    out = _read_all(bars_dir)
    assert sorted(out["close"]) == [9.0, 9.5]   # refreshed complete life wins


def test_compact_bars_daily_recovers_from_crashed_swap(tmp_path, monkeypatch):
    from nn_meta import download_universe as du
    bars_dir = tmp_path / "bars_daily"          # crashed mid-swap: dir absent,
    old_dir = tmp_path / "bars_daily.old"       # .old holds the real cache,
    old_dir.mkdir()                             # .compacting is partial output
    _bars_part(old_dir, "bars_part_0000.parquet", ["A"], [1.0])
    (tmp_path / "bars_daily.compacting").mkdir()
    monkeypatch.setattr(config, "BARS_DAILY_DIR", bars_dir)
    du.compact_bars_daily()
    assert not old_dir.exists()
    assert not (tmp_path / "bars_daily.compacting").exists()
    assert _read_all(bars_dir)["ticker"].tolist() == ["A"]


def test_main_compact_flag_is_standalone_and_offline(tmp_path, monkeypatch):
    from nn_meta import download_universe as du
    bars_dir = tmp_path / "bars_daily"
    bars_dir.mkdir()
    _bars_part(bars_dir, "bars_part_0000.parquet", ["A"], [1.0])
    _bars_part(bars_dir, "bars_part_0001.parquet", ["A"], [9.0])
    monkeypatch.setattr(config, "BARS_DAILY_DIR", bars_dir)
    monkeypatch.setattr(config, "ensure_dirs", lambda: None)
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)    # no key required
    monkeypatch.setattr("sys.argv", ["download_universe", "--compact"])
    du.main()
    out = _read_all(bars_dir)
    assert list(zip(out["ticker"], out["close"])) == [("A", 9.0)]


def test_main_bars_path_autocompacts_and_keeps_manifest(tmp_path, monkeypatch):
    from nn_meta import download_universe as du
    bars_dir = tmp_path / "bars_daily"
    bars_dir.mkdir()
    _bars_part(bars_dir, "bars_part_0000.parquet", ["A", "B"], [1.0, 2.0])
    _bars_part(bars_dir, "bars_part_0001.parquet", ["A"], [9.0])
    uni = tmp_path / "universe.parquet"
    pd.DataFrame({"ticker": ["A", "B"],
                  "life_start": ["2026-05-01"] * 2,
                  "life_end": ["2026-06-15"] * 2}).to_parquet(uni, index=False)
    manifest = tmp_path / "bars_done.txt"
    monkeypatch.setattr(config, "BARS_DAILY_DIR", bars_dir)
    monkeypatch.setattr(config, "UNIVERSE_PARQUET", uni)
    monkeypatch.setattr(config, "DONE_MANIFEST", manifest)
    monkeypatch.setattr(config, "ensure_dirs", lambda: None)
    monkeypatch.setattr(du, "bulk_download", lambda uni, key: None)
    monkeypatch.setenv("MASSIVE_API_KEY", "dummy")
    monkeypatch.setattr("sys.argv", ["download_universe", "--bars-and-surface-only"])
    du.main()
    out = _read_all(bars_dir)                   # cron path self-compacted
    assert sorted(zip(out["ticker"], out["close"])) == [("A", 9.0), ("B", 2.0)]
    assert sorted(manifest.read_text().split()) == ["A", "B"]   # untouched set


def test_load_daily_bars_streams_filters_and_dedupes(tmp_path, monkeypatch):
    from nn_meta import build_surface as bs
    bars_dir = tmp_path / "bars_daily"
    bars_dir.mkdir()
    d = pd.Timestamp("2026-06-01")
    exp_ok = d + pd.Timedelta(days=10)
    exp_far = d + pd.Timedelta(days=config.DTE_MAX + 50)
    pd.DataFrame({"ticker": ["OK", "FAR", "CHEAP"], "date": [d] * 3,
                  "open": 1.0, "high": 1.0, "low": 1.0,
                  "close": [5.0, 5.0, 0.0], "volume": [10, 10, 10],
                  "vwap": None, "transactions": None}) \
        .to_parquet(bars_dir / "bars_part_0000.parquet", index=False)
    pd.DataFrame({"ticker": ["OK"], "date": [d], "open": 1.0, "high": 1.0,
                  "low": 1.0, "close": [5.0], "volume": [10],
                  "vwap": None, "transactions": None}) \
        .to_parquet(bars_dir / "bars_part_0001.parquet", index=False)   # dup row
    uni = tmp_path / "universe.parquet"
    pd.DataFrame({"ticker": ["OK", "FAR", "CHEAP"], "underlying": ["SPY"] * 3,
                  "strike": [100.0] * 3,
                  "expiration": [exp_ok, exp_far, exp_ok],
                  "type": ["call"] * 3}).to_parquet(uni, index=False)
    monkeypatch.setattr(config, "BARS_DAILY_DIR", bars_dir)
    monkeypatch.setattr(config, "UNIVERSE_PARQUET", uni)
    out = bs.load_daily_bars()
    assert list(out["ticker"]) == ["OK"]        # far-dte + sub-premium filtered,
    assert len(out) == 1                        # duplicate (ticker,date) deduped
    assert {"underlying", "strike", "expiration", "type"} <= set(out.columns)


# ── renamed listings in the underlying crawl (added 2026-08-16) ──────────────

def test_underlying_daily_fetches_alias_stores_spec_symbol(tmp_path, monkeypatch):
    from nn_meta import download_universe as du
    requested: list[str] = []
    idx = pd.bdate_range("2026-06-01", periods=3)

    def fake_loader(symbol, start, end, interval, **kw):
        requested.append(symbol)
        return pd.DataFrame({"Open": 1.0, "High": 2.0, "Low": 0.5,
                             "Close": 1.5, "Volume": 100.0}, index=idx)

    monkeypatch.setattr(du.vbt_data_loader, "load_price_data_smart", fake_loader)
    monkeypatch.setattr(config, "UNDERLYINGS", ["SQ", "SPY"])
    monkeypatch.setattr(config, "UNDERLYING_DAILY_PARQUET",
                        tmp_path / "underlying_daily.parquet")
    und = du.download_underlying_daily(end="2026-06-10")
    assert requested == ["XYZ", "SPY"]          # SQ fetched under its new listing
    assert set(und["underlying"]) == {"SQ", "SPY"}   # stored on the trained symbol
    on_disk = pd.read_parquet(tmp_path / "underlying_daily.parquet")
    assert set(on_disk["underlying"]) == {"SQ", "SPY"}
