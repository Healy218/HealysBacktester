# tests/test_proposals.py
"""nn_meta/proposals.py: sweep/single consistency for every proposal engine.

The invariant that matters: replaying a frozen parameter set through
single_signals() must reproduce EXACTLY the sweep column it was frozen from —
otherwise the baseline's trades drift from what the sweep ranked.
"""
import numpy as np
import pandas as pd
import pytest

from nn_meta import config
from nn_meta.proposals import single_signals, sweep_signals


def _bars(days: int = 40) -> pd.DataFrame:
    idx_parts = [pd.date_range(f"2025-06-{2 + i:02d} 14:30", periods=26, freq="15min")
                 for i in range(min(days, 20))]
    idx = idx_parts[0]
    for p in idx_parts[1:]:
        idx = idx.append(p)
    n = len(idx)
    rng = np.random.default_rng(7)
    trend = np.linspace(0, 8, n)
    wave = 3 * np.sin(np.arange(n) / 9) + rng.normal(0, 0.4, n)
    close = 100 + trend + wave
    vol = 1000 + (500 * (1 + np.sin(np.arange(n) / 5))).astype(int)
    return pd.DataFrame({"Open": close - 0.1, "High": close + 0.4,
                         "Low": close - 0.4, "Close": close, "Volume": vol},
                        index=idx)


@pytest.mark.parametrize("strategy", config.PROPOSAL_STRATEGIES)
def test_sweep_shapes_and_single_replay(strategy):
    bars = _bars()
    ent, ext, s_ent, s_ext = sweep_signals(strategy, bars)
    assert isinstance(ent, pd.DataFrame) and isinstance(ext, pd.DataFrame)
    assert ent.shape == ext.shape and ent.shape[1] >= 1
    assert list(ent.index) == list(bars.index)

    # freeze the first sweep column and replay it
    col = ent.columns[0]
    names = [n or f"p{i}" for i, n in enumerate(ent.columns.names)]
    vals = col if isinstance(col, tuple) else (col,)
    params = {}
    for k, v in zip(names, vals):
        f = float(v)
        params[k] = int(f) if f == int(f) else f

    ent1, ext1, s1, x1 = single_signals(strategy, bars, params)
    assert ent1.shape[1] == 1 and ext1.shape[1] == 1
    pd.testing.assert_series_equal(ent1.iloc[:, 0], ent[col],
                                   check_names=False)
    pd.testing.assert_series_equal(ext1.iloc[:, 0], ext[col],
                                   check_names=False)
    if s_ent is not None and s1 is not None:
        pd.testing.assert_series_equal(s1.iloc[:, 0], s_ent[col],
                                       check_names=False)
