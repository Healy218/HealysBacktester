# SPDX-License-Identifier: CC-BY-NC-SA-4.0
# Adapted from RSI Probability Matrix [ChartPrime], © ChartPrime.
# https://www.tradingview.com/script/c25U5rsF-RSI-Probability-Matrix-ChartPrime/
# https://creativecommons.org/licenses/by-nc-sa/4.0/
# Changes: Python completed-bar numerical/state implementation, causal matrix
# snapshots and ambiguity diagnostics; chart graphics/dashboard drawing omitted.
"""Source-reference RSI counts, not corrected options performance evidence.

Pinned Pine v1 evaluates existing trades before new entries, checks the target
before the stop, and may re-enter on the same resolution bar. These semantics
are preserved explicitly. A bar touching both levels is flagged as ambiguous
even though the author's reference counters award a win. No fees, options
fills or profitable-strategy conclusions are inferred from those counters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math

import numpy as np
import pandas as pd

from v3 import pine_compat as pine
from v3._tv_trend_support import comparison_value as cmp
from v3._tv_trend_support import cross_over, cross_under, integer, pine_ohlc, validate_bars

COUNT_NAMES = ("long_wins", "long_losses", "short_wins", "short_losses")


@dataclass
class RsiProbabilityState:
    """Sequential reference-position state; counts become known on resolution.

    The step input's raw signals are mathematical RSI/SMA conditions before
    the source's flat-position gate. This separation permits state replay and
    makes suppressed mathematical conditions observable without changing them.
    """
    active_side: int = 0
    entry_rsi_bucket: int = 0
    target_price: float = 0.0
    stop_price: float = 0.0
    entry_price: float = 0.0
    counts: np.ndarray = field(default_factory=lambda: np.zeros((4, 101), dtype=np.int64))

    def step(self, *, high: float, low: float, close: float, rsi: float, atr: float,
             raw_long: bool, raw_short: bool, atr_multiplier: float) -> dict:
        """Observe one completed bar. Entry-bar extrema never resolve its trade."""
        resolution_side = self.active_side
        resolution_outcome, resolution_bucket, ambiguous = 0, -1, False
        if self.active_side:
            hit_target = (cmp(high) >= cmp(self.target_price) if self.active_side == 1
                          else cmp(low) <= cmp(self.target_price))
            hit_stop = (cmp(low) <= cmp(self.stop_price) if self.active_side == 1
                        else cmp(high) >= cmp(self.stop_price))
            ambiguous = bool(hit_target and hit_stop)
            if hit_target or hit_stop:
                # Deliberately target-first, exactly as Pine lines65–93.
                resolution_outcome = 1 if hit_target else -1
                resolution_bucket = self.entry_rsi_bucket
                row = (0 if self.active_side == 1 else 2) + (0 if hit_target else 1)
                self.counts[row, resolution_bucket] += 1
                self.active_side = 0
        if not resolution_outcome:
            resolution_side = 0
        long_signal = bool(raw_long and self.active_side == 0)
        short_signal = bool(raw_short and self.active_side == 0)
        long_entry = long_signal and not math.isnan(rsi) and not math.isnan(atr)
        short_entry = short_signal and not math.isnan(rsi) and not math.isnan(atr)
        entry_wins = entry_losses = entry_win_pct = np.nan
        # Both source condition values are computed before either entry block.
        # RSI crossover and crossunder cannot both be true on a real bar.
        for side, accepted in ((1, long_entry), (-1, short_entry)):
            if accepted:
                bucket = int(pine.round_half_up(rsi))
                if not 0 <= bucket <= 100:
                    raise ValueError("rounded RSI must index the source's0–100 matrix")
                self.active_side, self.entry_rsi_bucket = side, bucket
                self.entry_price = float(close)
                self.target_price = close + side * atr * atr_multiplier
                self.stop_price = close - side * atr * atr_multiplier
                row = 0 if side == 1 else 2
                entry_wins, entry_losses = (int(self.counts[row, bucket]),
                                            int(self.counts[row + 1, bucket]))
                total = entry_wins + entry_losses
                entry_win_pct = 100 * entry_wins / total if total else 0.0
        totals = self.counts.sum(axis=1)
        current_bucket = int(pine.round_half_up(rsi)) if not math.isnan(rsi) else -1
        result = {
            "raw_long_signal": bool(raw_long), "raw_short_signal": bool(raw_short),
            "long_entry_signal": long_signal, "short_entry_signal": short_signal,
            "long_entry": bool(long_entry), "short_entry": bool(short_entry),
            "long_exit": resolution_side == 1, "short_exit": resolution_side == -1,
            "active_side": self.active_side, "entry_rsi_bucket": self.entry_rsi_bucket,
            "entry_price": self.entry_price, "target_price": self.target_price,
            "stop_price": self.stop_price, "resolution_side": resolution_side,
            "resolution_outcome": resolution_outcome, "resolution_rsi_bucket": resolution_bucket,
            "ambiguous_resolution": ambiguous, "entry_prior_wins": entry_wins,
            "entry_prior_losses": entry_losses, "entry_prior_win_pct": entry_win_pct,
            "current_rsi_bucket": current_bucket, "resolved_total": int(totals.sum()),
        }
        for row, name in enumerate(COUNT_NAMES):
            result[f"total_{name}"] = int(totals[row])
            result[f"current_bucket_{name}"] = int(self.counts[row, current_bucket]) if current_bucket >= 0 else 0
        long_total, short_total = totals[0] + totals[1], totals[2] + totals[3]
        result["long_reference_win_pct"] = 100 * totals[0] / long_total if long_total else 0.0
        result["short_reference_win_pct"] = 100 * totals[2] / short_total if short_total else 0.0
        return result

    def snapshot(self) -> dict:
        """JSON-compatible state with detached count arrays for restart."""
        return {"state_version": 1, "source": "c25U5rsF/v1", "active_side": self.active_side,
                "entry_rsi_bucket": self.entry_rsi_bucket, "target_price": self.target_price,
                "stop_price": self.stop_price, "entry_price": self.entry_price,
                "counts": self.counts.tolist()}

    @classmethod
    def from_snapshot(cls, snapshot: dict) -> "RsiProbabilityState":
        if snapshot.get("state_version") != 1 or snapshot.get("source") != "c25U5rsF/v1":
            raise ValueError("incompatible probability-state snapshot")
        counts = np.asarray(snapshot["counts"])
        if counts.shape != (4, 101) or not np.issubdtype(counts.dtype, np.integer) or (counts < 0).any():
            raise ValueError("invalid probability count matrix")
        side = integer("active_side", snapshot["active_side"], -1, 1)
        bucket = integer("entry_rsi_bucket", snapshot["entry_rsi_bucket"], 0, 100)
        prices = [float(snapshot[name]) for name in ("target_price", "stop_price", "entry_price")]
        if not np.isfinite(prices).all():
            raise ValueError("invalid probability reference levels")
        return cls(side, bucket, *prices, counts.astype(np.int64, copy=True))


from v3._source_memo import memoized_source


@memoized_source
def rsi_probability_matrix(
    bars: pd.DataFrame, rsi_period: int = 14, signal_period: int = 14,
    oversold: int = 40, overbought: int = 60, atr_period: int = 14,
    atr_multiplier: float = 3.0, include_matrix: bool = False,
) -> pd.DataFrame:
    """Return mathematical signals, source entries/outcomes and causal counts.

    With include_matrix=True all404 RSI-bucket counts are returned for EVERY
    observation time. The default exposes totals/current-bucket counts and the
    entry-label probability as known then, without a final-chart backfill.
    """
    validate_bars(bars)
    rsi_period, signal_period = integer("rsi_period", rsi_period), integer("signal_period", signal_period)
    atr_period = integer("atr_period", atr_period)
    # Upstream thresholds/multiplier have no range restrictions; keep unusual
    # but finite settings reproducible rather than silently fixing the author.
    oversold = integer("oversold", oversold, -(2**63), 2**63 - 1)
    overbought = integer("overbought", overbought, -(2**63), 2**63 - 1)
    atr_multiplier = float(atr_multiplier)
    if not math.isfinite(atr_multiplier):
        raise ValueError("atr_multiplier must be finite")
    rsi = pine.rsi(bars.Close, rsi_period)
    signal = pine.sma(rsi, signal_period)
    atr = pine.atr(pine_ohlc(bars), atr_period)
    raw_long = cross_over(rsi, signal) & (cmp(rsi) < cmp(oversold))
    raw_short = cross_under(rsi, signal) & (cmp(rsi) > cmp(overbought))
    state = RsiProbabilityState()
    rows, matrices = [], []
    for i in range(len(bars)):
        row = state.step(high=float(bars.High.iloc[i]), low=float(bars.Low.iloc[i]),
                         close=float(bars.Close.iloc[i]), rsi=float(rsi.iloc[i]),
                         atr=float(atr.iloc[i]), raw_long=bool(raw_long.iloc[i]),
                         raw_short=bool(raw_short.iloc[i]), atr_multiplier=atr_multiplier)
        rows.append(row)
        if include_matrix:
            matrices.append(state.counts.copy().reshape(-1))
    # Empty results retain the same schema/dtypes as normal frames.
    prototype = RsiProbabilityState().step(high=0, low=0, close=0, rsi=np.nan,
                                          atr=np.nan, raw_long=False, raw_short=False, atr_multiplier=1)
    output = pd.DataFrame(rows, index=bars.index, columns=prototype)
    for name, value in prototype.items():
        output[name] = output[name].astype(bool if isinstance(value, bool)
                                          else int if isinstance(value, int) else float)
    output.insert(0, "atr", atr)
    output.insert(0, "signal", signal)
    output.insert(0, "rsi", rsi)
    if include_matrix:
        matrix = np.asarray(matrices, dtype=np.int64).reshape(len(bars), 404)
        columns = [f"{name}_rsi_{bucket:03}" for name in COUNT_NAMES for bucket in range(101)]
        output = pd.concat([output, pd.DataFrame(matrix, index=bars.index, columns=columns)], axis=1)
    return output
