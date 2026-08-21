"""The magnitude/EV head joining the v4 policy grid (2026-08-21).

Covers: the ``ev`` mode is opt-in and leaves the legacy grid bit-identical;
EV sizing reaches the mark-to-market ledger with per-trade size fractions the
ledger caps at the uniform slot; the bundle loader/scanner threshold on the
EV head only when the persisted policy says so. No TensorFlow, no LightGBM.
"""
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from nn_meta import config
from nn_meta.ev_sizing import ev_selected_rows
from nn_meta.mark_stream import execution_frames, stable_trade_id
from nn_meta.v4_accounting import AccountingDataError, mark_to_market_portfolio
from nn_meta.v4_evaluate import (Predictor, choose_policy, evaluate_policy,
                                 policy_predictions, _ledger_policy_metrics,
                                 winsor_bounds)
from nn_meta.v4_loader import V4Bundle, ensemble_ev, load_final_v4
from tests.test_v4_evaluate import _flip_fixture, _rows, _spec


class FakeReg:
    """Top-level so joblib can round-trip it."""
    def __init__(self, value):
        self.value = value

    def predict(self, x):
        return np.full(len(x), self.value)


class FakeClf:
    def __init__(self, value):
        self.value = value

    def predict_proba(self, x):
        p = np.full(len(x), self.value)
        return np.column_stack([1 - p, p])


# ── grid membership ──────────────────────────────────────────────────────────

def test_ev_mode_is_opt_in_and_legacy_grid_is_bit_identical():
    rows, pred = _rows(), np.array([0.8, 0.9, 0.1])
    a = choose_policy(rows, pred, _spec(), thresholds=[0.5])
    b = choose_policy(rows, pred, _spec(), thresholds=[0.5], ev_predictions=None)
    assert a == b
    assert len(a["candidate_sharpes"]) == 2          # filter + rank × one threshold


def test_ev_candidates_join_the_grid_and_can_win():
    rows = _rows()
    pred = np.array([0.5, 0.5, 0.5])                  # P(win) head says nothing
    ev = np.array([0.05, 0.70, -0.10])                # EV head: take the 0.80 trade only
    policy = choose_policy(rows, pred, _spec(), thresholds=[0.5],
                           ev_predictions=ev, ev_thresholds=[0.0])
    # 2 legacy + 1 ev candidate were tried; every one counts as a trial
    assert len(policy["candidate_sharpes"]) == 3
    ev_winner = policy["mode"] == config.EV_MODE
    assert ev_winner                                   # it skipped the -10% trade
    assert policy["metrics"]["n_kept"] == 1


def test_ev_length_mismatch_is_rejected():
    with pytest.raises(ValueError, match="ev prediction"):
        choose_policy(_rows(), np.array([0.8, 0.9, 0.1]), _spec(),
                      ev_predictions=np.array([0.1, 0.2]))


def test_policy_predictions_routes_by_mode():
    p = Predictor("gbt", lambda r: np.full(len(r), 0.6), lambda r: np.full(len(r), 0.2))
    rows = _rows()
    assert np.allclose(policy_predictions(p, rows, "rank"), 0.6)
    assert np.allclose(policy_predictions(p, rows, config.EV_MODE), 0.2)
    bare = Predictor("gbt", lambda r: np.full(len(r), 0.6))
    with pytest.raises(ValueError, match="magnitude head"):
        policy_predictions(bare, rows, config.EV_MODE)


def test_evaluate_policy_ev_matches_shared_metric_schema():
    m = evaluate_policy(config.EV_MODE, _rows(), np.array([0.1, 0.2, 0.3]), 0.0)
    assert set(m) >= {"n_kept", "total_return", "max_drawdown", "per_trade_sharpe"}


def test_winsor_bounds_are_train_quantiles():
    lo, hi = winsor_bounds(np.linspace(-1, 3, 401), (0.01, 0.99))
    assert -1 < lo < -0.9 and 2.9 < hi < 3


# ── ledger: per-trade sizing ─────────────────────────────────────────────────

def _ledger_fixture():
    df, preds, stream, spec = _flip_fixture()
    return df, stream, spec


def test_ledger_honors_size_fraction_and_caps_it_at_the_uniform_slot():
    df, stream, _ = _ledger_fixture()
    clean = df[df["symbol"].str.startswith("C")].copy()
    base_trades, marks = execution_frames(clean, stream)
    full, _ = mark_to_market_portfolio(base_trades, marks, max_concurrent=5,
                                       position_fraction=0.10)
    half_trades = base_trades.assign(size_fraction=0.05)
    half, _ = mark_to_market_portfolio(half_trades, marks, max_concurrent=5,
                                       position_fraction=0.10)
    # Half the size -> roughly half the return, same sign; never identical.
    assert 0 < half["total_return"] < full["total_return"]
    assert half["total_return"] == pytest.approx(full["total_return"] / 2, rel=0.05)
    # Above the uniform slot is a concentration the ledger refuses.
    with pytest.raises(AccountingDataError, match="size_fraction"):
        mark_to_market_portfolio(base_trades.assign(size_fraction=0.11), marks,
                                 max_concurrent=5, position_fraction=0.10)
    with pytest.raises(AccountingDataError, match="size_fraction"):
        mark_to_market_portfolio(base_trades.assign(size_fraction=0.0), marks,
                                 max_concurrent=5, position_fraction=0.10)


def test_ev_selected_rows_carry_capped_size_fractions():
    df, _, _ = _ledger_fixture()
    cands = df.assign(pred_ev=np.linspace(0.01, 0.5, len(df)))
    sel = ev_selected_rows(cands, config.MAX_CONCURRENT, config.PORTFOLIO_FRACTION)
    assert not sel.empty and "size_fraction" in sel.columns
    assert (sel["size_fraction"] > 0).all()
    assert (sel["size_fraction"] <= config.PORTFOLIO_FRACTION + 1e-12).all()


def test_ev_mode_flows_through_the_ledger_with_its_sizes():
    df, stream, spec = _ledger_fixture()
    ev = np.where(df["symbol"].str.startswith("C"), 0.3, -0.5)    # clean only
    m = _ledger_policy_metrics(df.reset_index(drop=True), ev, config.EV_MODE, 0.0,
                               stream)
    assert m["basis"] == "ledger" and m["n_kept"] == 10
    assert m["total_return"] > 0 and m["max_drawdown"] <= config.MAX_DRAWDOWN_CAP
    # Through choose_policy, the EV head that dodges the toxic trades is eligible
    # on the ledger even though its P(win) twin (which keeps them) is not.
    pwin = np.full(len(df), 0.9)
    policy = choose_policy(df, pwin, spec, thresholds=[0.5], mark_stream=stream,
                           ev_predictions=ev, ev_thresholds=[0.0])
    assert policy["mode"] == config.EV_MODE and policy["eligible"]
    assert policy["selection_basis"] == "ledger"


# ── loader / bundle ──────────────────────────────────────────────────────────

FEATURES = ["rsi14", "macd_hist"]


def _feat_rows(n=4):
    return pd.DataFrame({f: np.arange(n, dtype="float32") for f in FEATURES})


def test_ensemble_ev_averages_magnitude_heads_and_fails_closed():
    members = [{"model": FakeClf(0.5), "magnitude": FakeReg(0.1)},
               {"model": FakeClf(0.5), "magnitude": FakeReg(0.3)}]
    assert np.allclose(ensemble_ev("gbt", members, _feat_rows(), FEATURES), 0.2)
    with pytest.raises(ValueError, match="magnitude head"):
        ensemble_ev("gbt", [{"model": FakeClf(0.5)}], _feat_rows(), FEATURES)


def test_bundle_decision_score_follows_the_persisted_mode():
    members = [{"model": FakeClf(0.7), "magnitude": FakeReg(0.02)}]
    rank = V4Bundle("gbt", "rank", 0.5, FEATURES, True, members, {})
    ev = V4Bundle("gbt", config.EV_MODE, 0.05, FEATURES, True, members, {})
    assert np.allclose(rank.decision_score(_feat_rows()), 0.7)
    assert rank.keep_mask(_feat_rows()).all()
    assert np.allclose(ev.decision_score(_feat_rows()), 0.02)
    assert not ev.keep_mask(_feat_rows()).any()          # 0.02 < 0.05 EV threshold
    assert ev.has_magnitude_head


def _write_bundle(bundle_dir, mode, *, with_magnitude):
    bundle_dir.mkdir(parents=True)
    run_dir = bundle_dir / "v4-gbt-xs-s0"
    run_dir.mkdir()
    joblib.dump(FakeClf(0.6), run_dir / "model.joblib")
    if with_magnitude:
        joblib.dump(FakeReg(0.12), run_dir / "magnitude.joblib")
    (run_dir / "params.json").write_text("{}")
    (bundle_dir / "ensemble_config.json").write_text(json.dumps({
        "run_ids": ["v4-gbt-xs-s0"], "family": "gbt", "mode": mode,
        "threshold": 0.1, "features": FEATURES, "eligible": True}))
    return bundle_dir


def test_load_final_v4_roundtrips_the_magnitude_head(tmp_path):
    b = load_final_v4(_write_bundle(tmp_path / "b", config.EV_MODE, with_magnitude=True))
    assert b.has_magnitude_head
    assert np.allclose(b.ev(_feat_rows()), 0.12)
    assert b.keep_mask(_feat_rows()).all()               # 0.12 >= 0.1


def test_load_final_v4_ev_mode_fails_closed_without_magnitude_head(tmp_path):
    with pytest.raises(FileNotFoundError, match="magnitude head"):
        load_final_v4(_write_bundle(tmp_path / "b", config.EV_MODE, with_magnitude=False))


def test_legacy_bundle_without_magnitude_head_still_loads(tmp_path):
    b = load_final_v4(_write_bundle(tmp_path / "b", "rank", with_magnitude=False))
    assert not b.has_magnitude_head
    assert np.allclose(b.decision_score(_feat_rows()), 0.6)


# ── live scanner ─────────────────────────────────────────────────────────────

def test_scanner_picks_and_filters_on_the_decision_score():
    from nn_meta.live.v4_scan import best_per_signal, format_v4_alert
    batch = pd.DataFrame({"symbol": ["SPY", "SPY"], "strategy": ["rsi", "rsi"],
                          "dte": [5, 10], "entry_ts": pd.to_datetime(["2025-01-02"] * 2)})
    scores = np.array([0.70, 0.60])           # P(win) prefers DTE 5 ...
    ev = np.array([0.02, 0.15])               # ... the EV head prefers DTE 10
    legacy = best_per_signal(batch, scores)
    assert int(legacy.iloc[0].dte) == 5
    chosen = best_per_signal(batch, scores, ev)
    assert int(chosen.iloc[0].dte) == 10 and chosen.iloc[0].decision == pytest.approx(0.15)
    members = [{"model": FakeClf(0.6), "magnitude": FakeReg(0.15)}]
    bundle = V4Bundle("gbt", config.EV_MODE, 0.05, FEATURES, True, members, {})
    fresh = {"direction": 0, "param_label": "p", "spot": 500.0}
    _, msg = format_v4_alert(next(chosen.itertuples(index=False)), fresh, bundle, True)
    assert "EV +15.0%" in msg and "P(win) 60%" in msg
