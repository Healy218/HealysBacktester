"""V8 event signals: timing, holding exits and the PIT tercile rule."""
import numpy as np
import pandas as pd

from nn_meta import v8_event_signals as es

DAYS = ["2024-05-28", "2024-05-29", "2024-05-30", "2024-05-31", "2024-06-03"]


def test_event_signal_bar_targets_next_1030_execution():
    tau = pd.Series(pd.to_datetime(["2024-05-28 20:21Z",     # 16:21 ET Tue → exec Wed → bar Tue
                                    "2024-05-29 13:30Z",     # 09:30 ET Wed (<10:00) → exec Wed → bar Tue
                                    "2024-05-29 14:30Z",     # 10:30 ET Wed → exec Thu → bar Wed
                                    "2024-06-03 20:00Z"]))   # after the grid → -1
    assert list(es.event_signal_bar(tau, DAYS)) == [0, 0, 1, -1]


def test_reaction_bar_is_first_close_after_release():
    tau = pd.Series(pd.to_datetime(["2024-05-28 20:21Z", "2024-05-29 12:00Z"]))   # after close / pre-market
    assert list(es.reaction_bar(tau, DAYS)) == [1, 1]


def test_holding_exit_extends_with_new_signal():
    E = np.zeros((1, 10), bool); E[0, [1, 3]] = True
    X = es.holding_exits(E, 4)
    assert list(np.nonzero(X[0])[0]) == [7]          # 4 bars after the newest signal (3)


def test_tercile_uses_only_earlier_events():
    days = [d.date().isoformat() for d in pd.bdate_range("2024-01-01", periods=80)]
    bars = np.arange(40, 80)                             # 40 events, one per bar
    vals = np.arange(40, dtype=float)                    # rising values
    flag = es.trailing_tercile_flag(bars, vals, days, min_n=30)
    assert not flag[:30].any()                           # fewer than 30 earlier events
    assert flag[30:].all()                               # each new value tops its history
