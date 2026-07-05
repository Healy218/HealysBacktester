# tests/test_student_policy.py
"""nn_meta/student/policy.py: hysteresis state machine + trade extraction."""
import numpy as np
import pandas as pd

from nn_meta.student.policy import FLAT, LONG, SHORT, states_from_probs, trades_from_states


def _probs(seq):
    """Class-index sequence → one-hot-ish probability matrix."""
    p = np.full((len(seq), 3), 0.05)
    for i, s in enumerate(seq):
        p[i, s] = 0.9
    return p


class TestStatesFromProbs:
    def test_one_bar_flicker_suppressed(self):
        seq = [FLAT, FLAT, LONG, FLAT, FLAT, FLAT]
        out = states_from_probs(_probs(seq), min_bars=2)
        assert list(out) == [FLAT] * 6                # single LONG bar ignored

    def test_persistent_state_commits_after_min_bars(self):
        seq = [FLAT, LONG, LONG, LONG, LONG]
        out = states_from_probs(_probs(seq), min_bars=2)
        assert list(out) == [FLAT, FLAT, LONG, LONG, LONG]

    def test_min_bars_one_commits_immediately(self):
        seq = [FLAT, LONG, FLAT, SHORT]
        out = states_from_probs(_probs(seq), min_bars=1)
        assert list(out) == seq

    def test_direction_flip_needs_persistence_too(self):
        seq = [LONG, LONG, LONG, SHORT, SHORT, SHORT]
        out = states_from_probs(_probs(seq), min_bars=2)
        # LONG commits at bar 1 (2 consecutive), SHORT at bar 4
        assert list(out) == [FLAT, LONG, LONG, LONG, SHORT, SHORT]


class TestTradesFromStates:
    IDX = pd.date_range("2025-06-02 14:30", periods=10, freq="15min")

    def test_round_trip_long(self):
        states = np.array([FLAT, LONG, LONG, LONG, FLAT, FLAT, FLAT, FLAT, FLAT, FLAT])
        trades = trades_from_states(states, self.IDX)
        assert trades == [(self.IDX[1], self.IDX[4], 0)]

    def test_flip_closes_and_reopens(self):
        states = np.array([FLAT, LONG, LONG, SHORT, SHORT, FLAT, FLAT, FLAT, FLAT, FLAT])
        trades = trades_from_states(states, self.IDX)
        assert trades == [(self.IDX[1], self.IDX[3], 0),
                          (self.IDX[3], self.IDX[5], 1)]

    def test_open_trade_exits_at_final_bar(self):
        states = np.array([FLAT] * 8 + [SHORT, SHORT])
        trades = trades_from_states(states, self.IDX)
        assert trades == [(self.IDX[8], self.IDX[9], 1)]

    def test_all_flat_no_trades(self):
        assert trades_from_states(np.full(10, FLAT), self.IDX) == []

    def test_max_trades_cap(self):
        # alternating LONG/FLAT pairs → many trades; cap at 2
        states = np.array([LONG, FLAT] * 5)
        trades = trades_from_states(states, self.IDX, max_trades=2)
        assert len(trades) == 2
