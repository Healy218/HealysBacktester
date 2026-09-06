"""V4 live candidate-batch constructor and its parity comparator."""
import numpy as np
import pandas as pd
import pytest

from nn_meta.build_meta_dataset import V4_META_FEATURES
from nn_meta.live.v4_candidates import (assert_candidate_parity,
                                        build_candidate_batch)
from nn_meta.live.v4_parity import FeatureParityError


def _bars(days=6, per_day=26, seed=0):
    rng = np.random.default_rng(seed)
    idx = []
    for d in pd.bdate_range("2026-01-05", periods=days):
        idx += [d + pd.Timedelta(minutes=30) + pd.Timedelta(minutes=15 * b)
                for b in range(per_day)]
    idx = pd.DatetimeIndex(idx)
    close = 100 + np.cumsum(rng.normal(0, 0.1, len(idx)))
    return pd.DataFrame({"Open": close + rng.normal(0, 0.05, len(idx)),
                         "High": close + 0.1, "Low": close - 0.1,
                         "Close": close, "Volume": 1_000}, index=idx)


def _surface(sym="SPY"):
    return pd.DataFrame({
        "underlying": [sym, sym],
        "date": pd.to_datetime(["2026-01-05", "2026-01-06"]),
        "rvol_5": [0.15, 0.16], "rvol_21": [0.18, 0.18],
        "atm_iv_near": [0.20, 0.21], "atm_iv_far": [0.22, 0.22],
        "term_slope": [0.02, 0.01], "iv_chg_5": [0.0, 0.01],
        "pc_ratio": [0.9, 0.95]})


def _spec():
    return {"symbols": {"SPY": {"strategies": {"rsi": {"params": {}}}}}}


def _proposals(entry_ts):
    return pd.DataFrame({"symbol": ["SPY"], "strategy": ["rsi"], "dte": [5],
                        "direction": [1], "strike": [101.0],
                        "entry_ts": [pd.Timestamp(entry_ts)]})


def _entry_ts(bars):
    return bars.index[bars.index.normalize() == pd.Timestamp("2026-01-08")][10]


def test_batch_has_full_v4_schema_and_no_prem_spot():
    bars = _bars()
    batch = build_candidate_batch(_proposals(_entry_ts(bars)), {"SPY": bars},
                                  _surface(), _spec())
    assert set(V4_META_FEATURES) <= set(batch.columns)
    assert "prem_spot" not in batch.columns
    assert batch["strat_rsi"].iloc[0] == 1.0
    assert batch["sec_idx_etf"].iloc[0] == 1.0
    # Trade context is computable without any option fill.
    assert np.isfinite(batch["moneyness"].iloc[0])
    assert batch["dte_frac"].iloc[0] == pytest.approx(5 / 45)


def test_builder_is_deterministic_and_parity_holds():
    bars = _bars()
    props = _proposals(_entry_ts(bars))
    offline = build_candidate_batch(props, {"SPY": bars}, _surface(), _spec())
    live = build_candidate_batch(props, {"SPY": bars}, _surface(), _spec())
    assert_candidate_parity(offline, live)             # identical construction -> parity


def test_parity_fails_when_a_feature_drifts():
    bars = _bars()
    props = _proposals(_entry_ts(bars))
    offline = build_candidate_batch(props, {"SPY": bars}, _surface(), _spec())
    live = offline.copy()
    live.loc[0, "moneyness"] = live.loc[0, "moneyness"] + 0.01
    with pytest.raises(FeatureParityError, match="moneyness"):
        assert_candidate_parity(offline, live)


def test_context_merge_populates_cross_sectional_features():
    bars = _bars()
    context = pd.DataFrame({"underlying": ["SPY"],
                            "date": pd.to_datetime(["2026-01-06"]),
                            "market_iv": [0.19], "rv_iv_spread": [-0.02],
                            "beta_60d": [1.0]})
    batch = build_candidate_batch(_proposals(_entry_ts(bars)), {"SPY": bars},
                                  _surface(), _spec(), context=context)
    assert batch["beta_60d"].iloc[0] == pytest.approx(1.0)
    assert batch["market_iv"].iloc[0] == pytest.approx(0.19)


def test_missing_bar_raises():
    bars = _bars()
    props = _proposals("2020-01-01 10:00")   # before any bar
    with pytest.raises(ValueError, match="no underlying bars"):
        build_candidate_batch(props, {"SPY": bars}, _surface(), _spec())


def test_live_moneyness_matches_configured_offline_target_independent_of_strike(monkeypatch):
    from nn_meta import config
    monkeypatch.setitem(config.EXEC_CONFIG, "MONEYNESS", .02)
    bars = _bars()
    proposals = _proposals(_entry_ts(bars))
    first = build_candidate_batch(proposals, {"SPY": bars}, _surface(), _spec())
    proposals["strike"] = 2000.  # listed/executed strike never enters this feature
    second = build_candidate_batch(proposals, {"SPY": bars}, _surface(), _spec())
    assert first.moneyness.iloc[0] == pytest.approx(np.log1p(.02))
    assert_candidate_parity(first, second)
