# nn_meta/student/policy.py
"""Pure policy utilities: per-bar class probabilities → states → trades."""
from __future__ import annotations

import numpy as np
import pandas as pd

from nn_meta import config

FLAT, LONG, SHORT = 0, 1, 2


def states_from_probs(probs: np.ndarray,
                      min_bars: int = config.STUDENT_MIN_STATE_BARS) -> np.ndarray:
    """Argmax states with hysteresis: a new state must persist ``min_bars``
    consecutive raw bars before the committed state switches (kills 1-bar
    flicker that would spam untradable signals)."""
    raw = probs.argmax(axis=1).astype(np.int8)
    out = np.empty_like(raw)
    cur = FLAT
    pending, run = None, 0
    for i, s in enumerate(raw):
        if s == cur:
            pending, run = None, 0
        elif s == pending:
            run += 1
            if run >= min_bars:
                cur, pending, run = s, None, 0
        else:
            pending, run = s, 1
            if min_bars <= 1:
                cur, pending, run = s, None, 0
        out[i] = cur
    return out


def trades_from_states(states: np.ndarray, index: pd.DatetimeIndex,
                       max_trades: int = config.MAX_SIGNALS_PER_NAME
                       ) -> list[tuple[pd.Timestamp, pd.Timestamp, int]]:
    """(entry_ts, exit_ts, direction) from a committed state series.

    direction: 0 long / 1 short (executor convention). A long↔short flip
    closes one trade and opens the next on the same bar. An open trade at the
    end of the series exits at the final bar.
    """
    trades = []
    cur, entry_i = FLAT, None
    for i, s in enumerate(states):
        if s == cur:
            continue
        if cur != FLAT and entry_i is not None:
            trades.append((index[entry_i], index[i], 0 if cur == LONG else 1))
        entry_i = i if s != FLAT else None
        cur = s
        if len(trades) >= max_trades:
            break
    if cur != FLAT and entry_i is not None and len(trades) < max_trades:
        trades.append((index[entry_i], index[-1], 0 if cur == LONG else 1))
    return trades
