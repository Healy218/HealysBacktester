"""Magnitude labels and EV-based slot sizing (pure; no v31 data)."""
import numpy as np
import pandas as pd
import pytest

from nn_meta.ev_sizing import (bucket_expected_value, evaluate_ev,
                               ev_weighted_portfolio, portfolio_metrics_ev,
                               predicted_ev, return_bucket_labels)


def test_return_bucket_labels_carry_size():
    labels = return_bucket_labels([-0.9, -0.2, 0.3, 2.0])
    assert list(labels) == [0, 1, 2, 3]


def test_bucket_expected_value_and_predicted_ev():
    # All mass on the top bucket -> EV equals its midpoint.
    ev = bucket_expected_value([[0, 0, 0, 1.0]])
    assert ev[0] == pytest.approx(1.0)
    assert predicted_ev([0.5, 0.8], [0.2, 0.1]) == pytest.approx([0.10, 0.08])


def test_bucket_expected_value_shape_guard():
    with pytest.raises(ValueError, match="midpoints"):
        bucket_expected_value([[0.5, 0.5]])


def _two_trades(ev_a, ev_b, ret_a, ret_b):
    return pd.DataFrame({
        "symbol": ["SPY", "QQQ"], "strategy": ["rsi", "rsi"], "trade_idx": [1, 2],
        "entry_ts": pd.to_datetime(["2025-01-02", "2025-01-02"]),
        "exit_ts": pd.to_datetime(["2025-01-03", "2025-01-03"]),
        "net_return": [ret_a, ret_b], "pred_ev": [ev_a, ev_b],
    })


def test_ev_sizing_reduces_to_uniform_when_evs_are_equal():
    cands = _two_trades(0.1, 0.1, 0.2, 0.1)
    total, _, entered = ev_weighted_portfolio(cands, k=2, f=0.3)
    amounts = sorted(e[2] for e in entered)
    assert amounts == pytest.approx([0.3, 0.3])          # each at the uniform fraction
    assert total == pytest.approx(0.3 * 0.2 + 0.3 * 0.1)


def test_ev_sizing_de_risks_the_low_ev_name():
    # High-EV winner, low-EV loser: EV sizing shrinks the loser and beats uniform.
    cands = _two_trades(0.3, 0.05, 0.2, -0.4)
    ev_total, _, entered = ev_weighted_portfolio(cands, k=2, f=0.3)
    uniform_total = 0.3 * 0.2 + 0.3 * (-0.4)
    assert ev_total > uniform_total
    amt = {e[0]: e[2] for e in entered}
    assert amt[cands.index[0]] > amt[cands.index[1]]     # winner sized larger


def test_ev_sizing_respects_per_name_and_gross_caps():
    cands = _two_trades(0.9, 0.1, 0.1, 0.1)
    _, _, entered = ev_weighted_portfolio(cands, k=2, f=0.3)
    amounts = [e[2] for e in entered]
    assert max(amounts) <= 0.3 + 1e-9                    # per-name cap = f
    assert sum(amounts) <= 2 * 0.3 + 1e-9                # gross cap = k*f


def test_negative_ev_trades_are_not_entered():
    cands = _two_trades(0.2, -0.05, 0.1, 0.1)
    _, _, entered = ev_weighted_portfolio(cands, k=2, f=0.3)
    assert len(entered) == 1 and entered[0][0] == cands.index[0]


def test_evaluate_ev_matches_metrics_contract():
    cands = _two_trades(0.3, 0.1, 0.2, 0.1)
    metrics = evaluate_ev(cands, cands["pred_ev"].to_numpy(), 0.0, k=2, f=0.3)
    assert set(metrics) >= {"n_kept", "total_return", "max_drawdown", "win_rate",
                            "mean_return", "per_trade_sharpe", "total_ex_top3"}
    assert metrics["n_kept"] == 2
