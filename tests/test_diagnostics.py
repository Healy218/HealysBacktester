"""Score-decile diagnostic, including the v3.1 top-decile inversion pattern."""
import numpy as np
import pandas as pd

from nn_meta.diagnostics import (decile_diagnostic, score_decile_table,
                                 top_decile_inverted)


def _by_decile(win_rate_by_decile, win_value_by_decile, n=100):
    """Build rows with a fixed win rate and win magnitude per decile."""
    scores, rets = [], []
    for d, (p_win, win_val) in enumerate(zip(win_rate_by_decile, win_value_by_decile), 1):
        n_win = round(p_win * n)
        scores.extend([float(d)] * n)
        rets.extend([win_val] * n_win + [-0.02] * (n - n_win))
    return np.array(scores), np.array(rets)


def test_aligned_scores_are_not_inverted():
    # Win rate and win size both rise with score.
    win_rate = np.linspace(0.4, 0.9, 10)
    win_val = np.linspace(0.02, 0.10, 10)
    scores, rets = _by_decile(win_rate, win_val)
    table = score_decile_table(scores, rets)
    assert len(table) == 10
    assert table["win_rate"].iloc[-1] > table["win_rate"].iloc[0]
    assert not top_decile_inverted(table)


def test_detects_v31_top_decile_inversion():
    # Win rate rises with score, but win *size* shrinks as score rises, so mean
    # return falls: the confident top decile wins often but small (the v3.1 shape).
    win_rate = np.linspace(0.4, 0.9, 10)
    win_val = np.linspace(0.30, 0.01, 10)     # big winners at low scores, small at high
    scores, rets = _by_decile(win_rate, win_val)
    table = score_decile_table(scores, rets)
    assert table["win_rate"].iloc[-1] > table["win_rate"].iloc[0]   # win rate still rises
    assert table["mean_return"].iloc[0] > table["mean_return"].iloc[-1]  # but return inverts
    assert top_decile_inverted(table)


def test_decile_diagnostic_payload_shape():
    win_rate = np.linspace(0.4, 0.9, 10)
    scores, rets = _by_decile(win_rate, [0.03] * 10)
    payload = decile_diagnostic(scores, rets)
    assert set(payload) == {"inverted", "deciles"}
    assert len(payload["deciles"]) == 10
    assert set(payload["deciles"][0]) >= {"decile", "n", "mean_score",
                                          "win_rate", "mean_return"}


def test_sparse_input_returns_none_or_empty():
    assert decile_diagnostic([0.5], [0.1]) is None
    assert score_decile_table([np.nan, np.nan], [1.0, 2.0]).empty
