import copy

import pytest

from nn_meta import config
from nn_meta.multitimeframe_catalog import build_catalog, registered_catalog
from nn_meta.tradingview_proposals import SWEEP_GRIDS as SOURCE_GRIDS


def grids():
    return {k: v for k, v in config.SWEEP_GRIDS.items() if k not in SOURCE_GRIDS}


def test_full_registry_count_and_distinct_timeframe_identities():
    result = registered_catalog(["SPY", "QQQ"])
    assert result["families"]["ma"] == 2485
    assert result["families"]["macd"] == 51
    assert result["families"]["tv_setup"] == 6
    assert result["parameter_variants_per_timeframe"] == 2817
    assert result["variants_per_symbol"] == 11268
    assert result["symbol_timeframe_parameter_combinations"] == 22536
    assert len({r["variant_id"] for r in result["records"]}) == 11268
    assert result["ready_for_build"] is False
    assert all(r["params"]["fast_window"] < r["params"]["slow_window"]
               for r in result["records"] if r["strategy"] == "ma")


def test_inventory_identity_is_order_independent_and_binds_parameters():
    first = registered_catalog(["SPY", "QQQ"])
    second = build_catalog(["QQQ", "SPY"], dict(reversed(list(grids().items()))),
                           SOURCE_GRIDS, timeframes=(30, 15, 5, 1))
    assert first == second
    changed = copy.deepcopy(SOURCE_GRIDS)
    changed["tv_gaussian"]["gaussian_length"] = (15,)
    assert build_catalog(["SPY", "QQQ"], grids(), changed)["catalog_sha256"] != first["catalog_sha256"]


@pytest.mark.parametrize("symbols,timeframes", [([], (1,)), (["SPY", "SPY"], (1,)),
    (["SPY"], (1, 1)), (["SPY"], (2,)), (["SPY"], (True,)), (["SPY"], ())])
def test_invalid_inventory_fails_closed(symbols, timeframes):
    with pytest.raises(ValueError):
        build_catalog(symbols, grids(), SOURCE_GRIDS, timeframes=timeframes)


def test_changed_registry_requires_explicit_adapter():
    changed = grids()
    changed["rsi"] = {**changed["rsi"], "new_parameter": (1, 4, 1)}
    with pytest.raises(ValueError, match="grid keys"):
        build_catalog(["SPY"], changed, SOURCE_GRIDS)
