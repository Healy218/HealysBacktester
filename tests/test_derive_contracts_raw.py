"""Derivation keeps the all-observed chain and uses raw spot only for daily IV input."""
import json

import pandas as pd
import pytest

from nn_meta.price_basis import (PriceBasisError, raw_spot_provenance,
                                 require_raw_universe, require_raw_daily_options)
from v3.derive_contracts import derive_cache


def inputs(tmp_path, *, raw=True):
    cache = tmp_path / "input"
    (cache / "flatfiles_15m").mkdir(parents=True)
    # Near raw spot200 and far adjusted-like100 both remain in the universe.
    occ = ["SPY250613C00200000", "SPY250613C00100000"]
    frame = pd.DataFrame({"occ": [occ[0], occ[0], occ[1]], "Open": [1., 2., 1.],
                          "High": [2., 3., 2.], "Low": [.5, 1., .5],
                          "Close": [1.5, 2.5, 1.5], "Volume": [10., 20., 5.]})
    frame.to_parquet(cache / "flatfiles_15m/2025-06-02.parquet", index=False)
    daily = pd.DataFrame({"underlying": ["SPY"], "date": pd.to_datetime(["2025-06-02"]), "close": [200.]})
    daily.attrs = raw_spot_provenance("1d", provider="test", feed="explicit")
    if not raw: daily.attrs["adjustment"] = "all"
    daily.to_parquet(cache / "underlying_daily_raw.parquet", index=False)
    return cache


def test_raw_daily_filter_preserves_complete_universe_and_price_aggregation(tmp_path):
    cache = inputs(tmp_path)
    output = tmp_path / "new-output"
    manifest = derive_cache(cache, output)
    uni = pd.read_parquet(output / "universe.parquet")
    require_raw_universe(uni)
    assert set(uni.strike) == {100., 200.}
    assert uni.attrs["strike_filter"] == "none"
    part = pd.read_parquet(next((output / "bars_daily").glob("*.parquet")))
    require_raw_daily_options(part)
    assert part.ticker.tolist() == ["O:SPY250613C00200000"]
    assert part.open.iloc[0] == 1. and part.close.iloc[0] == 2.5
    assert part.volume.iloc[0] == 30.
    assert manifest["status"] == "complete" and manifest["universe_contracts"] == 2
    assert json.loads((output / "derivation_manifest.json").read_text())["output_sha256"]
    assert not (cache / "bars_daily").exists()


def test_derivation_rejects_existing_output_without_mutation(tmp_path):
    cache = inputs(tmp_path)
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "old-part"
    sentinel.write_text("untouched")
    with pytest.raises(ValueError, match="fresh directory"):
        derive_cache(cache, output)
    assert sentinel.read_text() == "untouched"


def test_derivation_rejects_adjusted_spot_even_in_raw_named_file(tmp_path):
    cache = inputs(tmp_path, raw=False)
    output = tmp_path / "fresh"
    with pytest.raises(PriceBasisError, match="adjustment"):
        derive_cache(cache, output)
    assert not output.exists()


def test_missing_raw_session_leaves_only_incomplete_isolated_output(tmp_path):
    cache = inputs(tmp_path)
    raw_path = cache / "underlying_daily_raw.parquet"
    frame = pd.read_parquet(raw_path)
    frame["date"] += pd.Timedelta(days=1)
    frame.to_parquet(raw_path, index=False)
    output = tmp_path / "fresh"
    with pytest.raises(ValueError, match="refusing silent contract drop"):
        derive_cache(cache, output)
    assert json.loads((output / "derivation_manifest.json").read_text())["status"] == "building"
    assert not (output / "universe.parquet").exists()


def test_surface_parts_cannot_mix_old_adjusted_filter_with_raw_filter(tmp_path):
    cache = inputs(tmp_path)
    output = tmp_path / "fresh"
    derive_cache(cache, output)
    part = pd.read_parquet(next((output / "bars_daily").glob("*.parquet")))
    part.attrs = {}
    with pytest.raises(PriceBasisError, match="rederive"):
        require_raw_daily_options(part)
