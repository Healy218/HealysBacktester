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
