"""v5 groundwork (2026-08-24): the wide strategy pool's proposal seam and the
PBO wiring in choose_policy — the two blockers cleared before the 300-ticker
generation."""
import numpy as np
import pandas as pd
import pytest

from nn_meta import config, proposals
from nn_meta.v4_evaluate import _grid_pbo, choose_policy


def _bars(n=1200, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-02 14:30", periods=n, freq="15min")
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n)))
    return pd.DataFrame({"Open": close, "High": close * 1.001,
                         "Low": close * 0.999, "Close": close,
                         "Volume": rng.integers(1000, 5000, n).astype(float)},
                        index=idx)


def test_every_v5_family_has_a_grid_and_a_sweep_path():
    bars = _bars()
    assert len(config.PROPOSAL_STRATEGIES_V5) == 10
    for strat in config.PROPOSAL_STRATEGIES_V5:
        assert strat in config.SWEEP_GRIDS, strat
        entries, exits, s_ent, s_ext = proposals.sweep_signals(strat, bars)
        assert entries is not None and exits is not None, strat
        assert len(entries) == len(bars), strat
        assert entries.select_dtypes(exclude=bool).empty \
            if isinstance(entries, pd.DataFrame) else entries.dtype == bool, strat


def _policy_rows(n_days=60, n_per_day=4, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(n_days):
        day = pd.Timestamp("2025-01-02") + pd.Timedelta(days=d)
        for k in range(n_per_day):
            ts = day + pd.Timedelta(hours=15, minutes=15 * k)
            rows.append({"symbol": f"S{k}", "strategy": "ma", "trade_idx": d,
                         "dte": 5, "entry_ts": ts,
                         "exit_ts": ts + pd.Timedelta(days=2),
                         "net_return": float(rng.normal(0.01, 0.05)),
                         "executed": True})
    return pd.DataFrame(rows)


def test_choose_policy_reports_pbo():
    rows = _policy_rows()
    spec = {"symbols": {f"S{k}": {"strategies": {"ma": {"dte": 5}}}
                        for k in range(4)}}
    pred = np.random.default_rng(2).uniform(0.3, 0.9, len(rows))
    winner = choose_policy(rows, pred, spec, thresholds=[0.4, 0.5, 0.6])
    p = winner.get("pbo")
    assert p is not None
    assert 0.0 <= p["pbo"] <= 1.0
    assert p["n_days"] == 60 and p["n_combinations"] > 100


def test_grid_pbo_never_guesses_on_thin_windows():
    rows = _policy_rows(n_days=8)
    fmask = np.ones(len(rows), dtype=bool)
    pred = np.full(len(rows), 0.7)
    cands = [{"mode": "filter", "threshold": 0.5},
             {"mode": "rank", "threshold": 0.5}]
    assert _grid_pbo(rows, fmask, pred, None, cands) is None   # < 16 days


def test_v6_adds_keltner_and_bbw_squeeze_on_top_of_v5():
    """v6 = v5's ten + two band families, each with a grid and a sweep path;
    v5's list is untouched (its deployed spec hash must stay stable)."""
    from nn_meta import proposals as pr
    assert config.PROPOSAL_STRATEGIES_V6[:10] == config.PROPOSAL_STRATEGIES_V5
    assert config.PROPOSAL_STRATEGIES_V6[10:] == ["keltner", "bbw_squeeze"]
    bars = _bars(n=1500)
    for strat in ("keltner", "bbw_squeeze"):
        assert strat in config.SWEEP_GRIDS
        entries, exits, s_ent, s_ext = pr.sweep_signals(strat, bars)
        assert len(entries) == len(bars) and entries.dtypes.eq(bool).all()
        assert entries.columns.nlevels == 2
        assert entries.values.any(), f"{strat}: no long entries on random walk"
        assert exits.values.any()
        # the frozen-params path re-creates the winning column from its levels
        col = entries.columns[entries.sum().argmax()]
        names = list(entries.columns.names)
        single = pr.single_signals(strat, bars, dict(zip(names, col)))
        assert single[0].shape[0] == len(bars)
