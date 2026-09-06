"""Four-frame proposal adapter for ChartPrime's source-reference signals.

Entries reproduce the source's one-position gate; exits flag reference
target/stop resolution bars. Its target-first win counters do not determine
options fills, ledger labels or economic acceptance. Numerical TV parity is
still pending and this adapter is not admitted to an active pool.
"""
from itertools import product

from signals.tv_signals import _assemble
from v3.tv_rsi_probability import rsi_probability_matrix


def generate_rsi_probability_signals(
    ohlcv, rsi_range, signal_range, atr_multiplier_range,
    enable_shorting=False, **fixed_inputs,
):
    out = {}
    for rsi_period, signal_period, multiplier in product(rsi_range, signal_range, atr_multiplier_range):
        result = rsi_probability_matrix(ohlcv, rsi_period=int(rsi_period),
                                        signal_period=int(signal_period),
                                        atr_multiplier=float(multiplier), **fixed_inputs)
        out[(int(rsi_period), int(signal_period), float(multiplier))] = (
            result.long_entry, result.long_exit, result.short_entry, result.short_exit)
    return _assemble(out, ["rpm_rsi", "rpm_signal", "rpm_atr_mult"], enable_shorting)
