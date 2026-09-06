"""Raw stock spot/strike basis and selection-time regressions."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from nn_meta import baseline, build_surface, config, price_basis
from nn_meta.price_basis import PriceBasisError, raw_spot_provenance, require_raw_panel
from options.execution import Execution, execute_trade_returns
from options.selection.contract_selector import select_contract
from options.data.provider import OptionContract
from tests.test_execution import SyntheticProvider, DAYS, _underlying


def daily(close=200., periods=30):
    frame = pd.DataFrame({"underlying": "SPY", "date": pd.bdate_range("2025-05-01", periods=periods),
                          "open": close, "close": close, "volume": 1000.})
    frame.attrs = raw_spot_provenance("1d", provider="test", feed="explicit")
    return frame


def raw_series(index, value=200., symbol="SPY"):
    close = pd.Series(value, index=index, name="Close")
    close.attrs = dict(raw_spot_provenance("15m", provider="test", feed="explicit"), symbol=symbol)
    return close


def option_bars(day):
    return pd.DataFrame({"underlying": "SPY", "date": pd.to_datetime([day] * 4),
                          "expiration": pd.to_datetime([day + pd.Timedelta(days=n) for n in (5, 30, 5, 30)]),
                          "strike": [200., 200., 100., 100.], "close": [2., 3., 2., 3.],
                          "type": ["call", "put", "call", "put"], "volume": [100., 150., 10., 20.]})


def test_surface_iv_uses_raw_spot_while_return_features_keep_adjusted_history(monkeypatch):
    raw = daily(200.)
    adjusted = daily(100.)
    adjusted.attrs = {"adjustment": "all"}
    seen = []
    def iv(price, spot, strike, dte, is_call):
        seen.append((spot.copy(), strike.copy()))
        return np.full(len(spot), .25)
    monkeypatch.setattr(build_surface, "implied_vol", iv)
    result = build_surface.build_surface(option_bars(raw.date.iloc[-1]), adjusted, raw_spot=raw)
    assert seen[0][0].tolist() == [200., 200.]
    assert seen[0][1].tolist() == [200., 200.]
    assert result.atm_iv_near.iloc[-1] == .25
    assert result.atm_iv_far.iloc[-1] == .25
    assert result.rvol_21.iloc[-1] == 0.
    assert result.attrs["option_strike_spot_basis"] == "raw"
    assert result.attrs["raw_spot_provenance"]["provider"] == "test"


def test_surface_rejects_missing_raw_input_or_adjusted_metadata():
    adjusted = daily(100.)
    adjusted.attrs["adjustment"] = "all"
    ob = option_bars(adjusted.date.iloc[-1])
    with pytest.raises(PriceBasisError, match="required"):
        build_surface.build_surface(ob, adjusted)
    with pytest.raises(PriceBasisError, match="adjustment"):
        build_surface.build_surface(ob, adjusted, raw_spot=adjusted)


def test_surface_missing_raw_date_is_error_instead_of_silent_row_drop():
    raw = daily()
    with pytest.raises(ValueError, match="raw daily spot missing"):
        build_surface.build_surface(option_bars(raw.date.iloc[-1]), daily(100.), raw_spot=raw.iloc[:-1])


def test_surface_single_option_right_keeps_ratio_unavailable():
    raw = daily()
    ob = option_bars(raw.date.iloc[-1])
    result = build_surface.build_surface(ob[ob.type == "call"], daily(100.), raw_spot=raw)
    assert result.pc_ratio.isna().all()


@pytest.mark.parametrize("change", ["metadata", "basis", "duplicate", "nonpositive", "infinite", "timestamp", "symbol"])
def test_raw_panel_rejects_unverifiable_prices_or_keys(change):
    raw = daily()
    if change == "metadata": raw.attrs = {}
    elif change == "basis": raw.attrs["price_basis"] = "adjusted"
    elif change == "duplicate": raw = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)
    elif change == "nonpositive": raw.loc[0, "close"] = 0.
    elif change == "infinite": raw.loc[0, "close"] = np.inf
    elif change == "timestamp": raw["date"] = raw.date.dt.tz_localize("UTC")
    elif change == "symbol": raw.loc[0, "underlying"] = ""
    with pytest.raises(PriceBasisError): require_raw_panel(raw, "1d")


def test_raw_intraday_loader_preserves_identity_and_requires_exact_coverage(tmp_path, monkeypatch):
    index = pd.date_range("2025-06-02 14:30", periods=3, freq="15min")
    panel = pd.DataFrame({"symbol": "SPY", "timestamp": index, "Close": [200., 201., 202.]})
    panel.attrs = raw_spot_provenance("15m", provider="test", feed="explicit")
    path = tmp_path / "raw.parquet"
    panel.to_parquet(path, index=False)
    monkeypatch.setattr(config, "UNDERLYING_15M_RAW_PARQUET", path)
    got = price_basis.load_raw_close_15m("SPY", index=index)
    assert got.tolist() == [200., 201., 202.]
    assert got.attrs["symbol"] == "SPY" and got.attrs["price_basis"] == "raw"
    with pytest.raises(PriceBasisError, match="missing1|missing 1"):
        price_basis.load_raw_close_15m("SPY", index=index.append(pd.DatetimeIndex([index[-1] + pd.Timedelta(minutes=15)])))
    panel.attrs["adjustment"] = "all"
    panel.to_parquet(path, index=False)
    with pytest.raises(PriceBasisError, match="adjustment"):
        price_basis.load_raw_close_15m("SPY", index=index)


def test_missing_raw_cache_has_no_adjusted_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UNDERLYING_15M_RAW_PARQUET", tmp_path / "absent.parquet")
    with pytest.raises(FileNotFoundError, match="separate raw"):
        price_basis.load_raw_close_15m("SPY")


def test_baseline_chain_bounds_and_blotter_use_raw_not_technical_price():
    _, index = _underlying()
    bars = pd.DataFrame({c: 100. for c in ("Open", "High", "Low", "Close")}, index=index)
    bars["Volume"] = 100.
    class RecordingProvider(SyntheticProvider):
        bounds = None
        def get_chain(self, underlying, **kwargs):
            self.bounds = kwargs["strike_gte"], kwargs["strike_lte"]
            return super().get_chain(underlying, **kwargs)
    provider = RecordingProvider(DAYS, ["2025-06-13"], strike=200.)
    ex = Execution("SPY", "15m", "2025-06-30", provider, {"FILL_SAME_BAR": True})
    rows, meta = baseline.execute_at_dte("SPY", [(index[0], index[51], 0)], bars, 5,
                                        provider, "2025-06-30", ex=ex, collect_marks=True,
                                        raw_close=raw_series(index))
    assert provider.bounds == pytest.approx((170., 230.))
    assert rows[0]["strike"] == 200.
    assert rows[0]["fill_entry_ts"] > index[0]
    assert meta["blotter"][0][0]["selection_spot"] == 200.
    assert meta["blotter"][0][0]["selection_spot_basis"] == "raw"


def test_baseline_rejects_wrong_symbol_and_adjusted_series_before_chain_lookup():
    _, index = _underlying()
    bars = pd.DataFrame({"Close": 100.}, index=index)
    raw = raw_series(index, symbol="QQQ")
    with pytest.raises(ValueError, match="symbol differs"):
        baseline.execute_at_dte("SPY", [], bars, 5, None, "2025-06-30", raw_close=raw)
    raw.attrs["symbol"], raw.attrs["adjustment"] = "SPY", "all"
    with pytest.raises(PriceBasisError):
        baseline.execute_at_dte("SPY", [], bars, 5, None, "2025-06-30", raw_close=raw)


def test_selector_raw_basis_gate_precedes_even_delta_selection():
    chain = [OptionContract(symbol="SPY250613C00200000", underlying="SPY", expiration=date(2025, 6, 13),
                            strike=200., right="C", delta=.5)]
    for kwargs in ({"spot_basis": "adjusted"}, {"require_raw_spot": True}):
        with pytest.raises(ValueError, match="raw"):
            select_contract(chain, right="C", spot=200., as_of=date(2025, 6, 2), **kwargs)
    assert select_contract(chain, right="C", spot=200., as_of=date(2025, 6, 2),
                            spot_basis="raw", require_raw_spot=True) is chain[0]


def test_every_roll_fill_waits_until_raw_selection_close_is_known():
    _, index = _underlying()
    close = raw_series(index, value=100.)
    provider = SyntheticProvider(DAYS, ["2025-06-05", "2025-06-13"])
    ex = Execution("SPY", "15m", "2025-06-30", provider, {"REQUIRE_RAW_SPOT": True})
    _, meta = execute_trade_returns(ex, [(index[26], index[207], 0)], close, index, 2, collect_marks=True)
    assert meta["n_rolls"] >= 1
    for leg in meta["blotter"][0]:
        assert pd.Timestamp(leg["entry"]) >= pd.Timestamp(leg["selection_bar_ts"]) + pd.Timedelta(minutes=15)


def test_old_surface_provenance_is_rejected_by_feature_loader(tmp_path, monkeypatch):
    from nn_meta.build_meta_dataset import load_surface_features
    raw = daily()
    surface = build_surface.build_surface(option_bars(raw.date.iloc[-1]), daily(100.), raw_spot=raw)
    path = tmp_path / "surface.parquet"
    monkeypatch.setattr(config, "SURFACE_DATASET_PARQUET", path)
    surface.to_parquet(path, index=False)
    assert load_surface_features().attrs["option_strike_spot_basis"] == "raw"
    surface.attrs = {}
    surface.to_parquet(path, index=False)
    with pytest.raises(PriceBasisError, match="raw-spot provenance"):
        load_surface_features()


def test_historical_provider_rejects_old_adjusted_filter_universe(tmp_path, monkeypatch):
    from nn_meta.providers import get_provider
    path = tmp_path / "universe.parquet"
    pd.DataFrame({"ticker": ["SPY250613C00200000"]}).to_parquet(path, index=False)
    monkeypatch.setattr(config, "UNIVERSE_PARQUET", path)
    with pytest.raises(PriceBasisError, match="strike-filter provenance"):
        get_provider()


def test_raw_universe_filter_tags_the_actual_new_contract_scope(tmp_path, monkeypatch):
    from nn_meta import download_universe as du
    frame = daily()
    contracts = pd.DataFrame({"ticker": ["SPY250613C00200000", "SPY250613C00020000"],
                              "underlying": "SPY", "strike": [200., 20.], "type": "call",
                              "expiration": pd.to_datetime(["2025-06-13"] * 2)})
    monkeypatch.setattr(config, "UNIVERSE_PARQUET", tmp_path / "universe.parquet")
    result = du.build_universe(contracts, frame)
    assert result.strike.tolist() == [200.]
    restored = pd.read_parquet(config.UNIVERSE_PARQUET, columns=[])
    price_basis.require_raw_universe(restored)
    adjusted = frame.copy()
    adjusted.attrs["adjustment"] = "all"
    with pytest.raises(PriceBasisError):
        du.build_universe(contracts, adjusted)


def test_explicit_raw_alias_uses_exact_root_first_and_never_fills_missing_dates():
    frame = pd.DataFrame({"underlying": ["NEW", "OLD"], "date": pd.to_datetime(["2025-06-02"] * 2),
                          "close": [200., 201.]})
    frame.attrs = raw_spot_provenance("1d", provider="test", feed="explicit")
    resolved = price_basis.raw_daily_for_roots(frame, {"OLD": "NEW", "ALIAS": "NEW"})
    assert resolved.loc[resolved.underlying == "OLD", "close"].tolist() == [201.]
    assert resolved.loc[resolved.underlying == "ALIAS", "close"].tolist() == [200.]
    assert resolved.attrs["resolved_root_aliases"]["ALIAS"]["sessions_added"] == 1
    assert "OLD" not in resolved.attrs["resolved_root_aliases"]
    assert len(frame) == 2
    assert resolved.date.unique().tolist() == [pd.Timestamp("2025-06-02")]
