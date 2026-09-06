"""Historical materialization must never change sealed research inputs."""
from datetime import date, timedelta
import hashlib

import pandas as pd
import pytest

from nn_meta import config
from nn_meta.price_basis import RAW_SPOT_SCHEMA_VERSION
from nn_meta.providers import get_provider
from options.data.hybrid_provider import HybridCachedProvider
from utils.error_handling import DataError
from v3.flatfiles import FlatFilesProvider

CALL = "SPY250103C00600000"
PUT = "SPY250103P00600000"


def _universe():
    frame = pd.DataFrame({"ticker": ["O:" + CALL, "O:" + PUT], "underlying": "SPY",
                          "expiration": pd.Timestamp("2025-01-03"), "life_start": pd.Timestamp("2025-01-02"),
                          "strike": 600., "type": ["call", "put"]})
    frame.attrs = {"universe_price_basis_schema": RAW_SPOT_SCHEMA_VERSION,
                   "contract_scope": "all_observed_contracts", "source": "flatfiles_15m",
                   "strike_filter": "none", "derivation_provenance": "synthetic test"}
    return frame


def _inventory(root):
    return {str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns,
                                       hashlib.sha256(p.read_bytes()).hexdigest())
            for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    sealed = tmp_path / "sealed"
    sealed.mkdir()
    _universe().to_parquet(sealed / "universe.parquet", index=False)
    frames = sealed / "flatfiles_15m"
    frames.mkdir()
    for day in ("2025-01-02", "2025-01-03"):
        pd.DataFrame({"occ": [CALL, CALL], "timestamp": pd.date_range(day + " 14:30", periods=2, freq="15min"),
                      "Open": [1., 2.], "High": [2., 3.], "Low": [.5, 1.5],
                      "Close": [1.5, 2.5], "Volume": [10, 20]}).to_parquet(frames / (day + ".parquet"), index=False)
    legacy = pd.DataFrame({"Open": 5., "High": 6., "Low": 4., "Close": 5.5, "Volume": 100},
                          index=pd.date_range("2025-01-02 14:30", periods=3, freq="15min", name="timestamp"))
    legacy.attrs["provenance"] = "sealed existing contract cache"
    (sealed / "bars_15m").mkdir()
    legacy.to_parquet(sealed / "bars_15m" / (PUT + ".parquet"))
    monkeypatch.setattr(config, "CAMPAIGN", "synthetic-campaign")
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "campaign" / "runs")
    monkeypatch.setattr(config, "DATA_CACHE", sealed)
    monkeypatch.setattr(config, "UNIVERSE_PARQUET", sealed / "universe.parquet")
    monkeypatch.setattr(config, "UNDERLYING_DAILY_PARQUET", sealed / "underlying_daily.parquet")
    monkeypatch.setattr(config, "UNDERLYING_15M_PARQUET", sealed / "underlying_15m.parquet")
    monkeypatch.setattr(config, "_BIG_RUN", True)
    return sealed, legacy


def test_miss_materializes_only_in_campaign_and_all_cache_reads_match(campaign):
    sealed, legacy = campaign
    before = _inventory(sealed)
    provider = get_provider()
    assert isinstance(provider, FlatFilesProvider)
    first = provider.get_contract_bars(CALL, "2025-01-02", "2025-01-02", "15m")
    assert len(first) == 2 and provider.cache_counts["materialized"] == 1
    writable = config.RUNS_DIR / "provider_cache" / "bars_15m" / (CALL + ".parquet")
    assert writable.is_file()
    cached = provider.get_contract_bars(CALL, "2025-01-02", "2025-01-02", "15m")
    pd.testing.assert_frame_equal(first, cached)
    full = provider.get_contract_bars(CALL, "2025-01-02", "2025-01-03", "15m")
    assert len(full) == 4  # full life cached even when first request was one day
    fallback = provider.get_contract_bars(PUT, "2025-01-02", "2025-01-02", "15m")
    pd.testing.assert_frame_equal(fallback, legacy, check_freq=False)
    assert fallback.attrs == legacy.attrs
    assert not (writable.parent / (PUT + ".parquet")).exists()  # no promotion/copy
    assert provider.cache_counts == {"writable_hit": 2, "readonly_hit": 1, "materialized": 1}
    assert _inventory(sealed) == before
    restarted = get_provider(allow_fetch=False)
    pd.testing.assert_frame_equal(first, restarted.get_contract_bars(CALL, "2025-01-02", "2025-01-02", "15m"))
    pd.testing.assert_frame_equal(legacy, restarted.get_contract_bars(PUT, "2025-01-02", "2025-01-02", "15m"), check_freq=False)
    assert _inventory(sealed) == before


def test_empty_and_daily_materializations_preserve_sealed_inventory(campaign):
    sealed, _ = campaign
    before = _inventory(sealed)
    provider = get_provider()
    daily = provider.get_contract_bars(CALL, "2025-01-02", "2025-01-03", "daily")
    assert daily.Close.tolist() == [2.5, 2.5] and daily.Volume.tolist() == [30, 30]
    missing = "SPY250103C00700000"
    assert provider.get_contract_bars(missing, "2025-01-02", "2025-01-03", "15m").empty
    assert provider.get_contract_bars(missing, "2025-01-02", "2025-01-03", "15m").empty
    assert provider.cache_counts["materialized"] == 2 and provider.cache_counts["writable_hit"] == 1
    assert _inventory(sealed) == before


def test_life_index_uses_one_underlying_read_and_no_full_universe(campaign, monkeypatch):
    provider = get_provider()
    reads = []
    read = pd.read_parquet
    def watched(path, *args, **kwargs):
        reads.append(kwargs.get("filters"))
        return read(path, *args, **kwargs)
    monkeypatch.setattr(pd, "read_parquet", watched)
    monkeypatch.setattr(provider, "_get_universe", lambda: pytest.fail("full universe must not load"))
    for _ in range(3):
        assert provider._life_window(CALL) == (date(2025, 1, 2), date(2025, 1, 3))
        assert provider._life_window(PUT) == (date(2025, 1, 2), date(2025, 1, 3))
    assert reads == [[("underlying", "==", "SPY")]]
    assert provider._universe is None


def test_life_index_preserves_first_duplicate_and_renamed_root_fallback(tmp_path):
    universe = _universe()
    duplicate = universe.iloc[[0]].copy()
    duplicate["life_start"] = pd.Timestamp("2024-11-01")
    renamed = universe.iloc[[0]].copy()
    renamed["ticker"] = "O:SQ250103C00600000"
    renamed["underlying"] = "XYZ"
    renamed["life_start"] = pd.Timestamp("2024-06-01")
    path = tmp_path / "universe.parquet"
    pd.concat([universe, duplicate, renamed], ignore_index=True).to_parquet(path)
    provider = HybridCachedProvider(universe_parquet=path, bars_cache_dir=tmp_path / "out")
    assert provider._life_window(CALL) == (date(2025, 1, 2), date(2025, 1, 3))
    assert provider._life_window("SQ250103C00600000") == (date(2024, 6, 1), date(2025, 1, 3))
    missing = "QQQ250103C00600000"
    assert provider._life_window(missing) == (date(2025, 1, 3) - timedelta(days=75), date(2025, 1, 3))
    assert provider._universe is None


def test_named_campaign_rejects_writable_override_into_sealed_cache(campaign):
    sealed, _ = campaign
    with pytest.raises(ValueError, match="RUNS_DIR/provider_cache"):
        get_provider(bars_cache_dir=sealed)
    with pytest.raises(DataError, match="outside readonly"):
        HybridCachedProvider(bars_cache_dir=sealed / "bad", bars_readonly_cache_dirs=(sealed,))


@pytest.mark.parametrize("occ,interval", [("../../outside", "15m"), (CALL, "../../outside"), (CALL, "15m/../secret")])
def test_cache_keys_cannot_escape_writable_or_readonly_roots(campaign, occ, interval):
    with pytest.raises(DataError, match="Unsafe"):
        get_provider().get_contract_bars(occ, "2025-01-02", "2025-01-03", interval)


def test_readonly_contract_symlink_cannot_escape_sealed_root(campaign, tmp_path):
    sealed, _ = campaign
    outside = tmp_path / "outside.parquet"
    pd.DataFrame({"secret": [1]}).to_parquet(outside)
    (sealed / "bars_15m" / (CALL + ".parquet")).symlink_to(outside)
    with pytest.raises(DataError, match="escapes"):
        get_provider().get_contract_bars(CALL, "2025-01-02", "2025-01-03", "15m")


def test_materialization_directory_symlink_cannot_enter_sealed_root(campaign):
    sealed, _ = campaign
    writable = config.RUNS_DIR / "provider_cache"
    writable.mkdir(parents=True)
    (writable / "bars_15m").symlink_to(sealed / "bars_15m", target_is_directory=True)
    before = _inventory(sealed)
    with pytest.raises(DataError, match="escapes"):
        get_provider().get_contract_bars(CALL, "2025-01-02", "2025-01-03", "15m")
    assert _inventory(sealed) == before


def test_live_and_unnamed_provider_cache_location_is_unchanged(campaign, monkeypatch):
    sealed, _ = campaign
    live = get_provider(live=True)
    assert type(live) is HybridCachedProvider and live._cache_dir == sealed
    assert live._readonly_cache_dirs == ()
    monkeypatch.setattr(config, "CAMPAIGN", "")
    historical = get_provider()
    assert historical._cache_dir == sealed and historical._readonly_cache_dirs == ()
