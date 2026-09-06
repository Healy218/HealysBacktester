"""Source accepted per-setup alerts, with reference-resolution exits.

The four boolean frames represent one reference position. The numerical source
book supports concurrency, but that is outside this wrapper's execution shape.
No exported Pine parity or active-pool admission is implied.
"""
from itertools import product

from signals.tv_signals import _assemble
from v3.tv_setup_scanner import SETUPS, setup_scanner


def generate_setup_scanner_signals(ohlcv, stop_atr_range, max_bars_range,
                                  enable_shorting=False, setup_names=SETUPS, **fixed_inputs):
    if fixed_inputs.get("max_open", 1) != 1:
        raise ValueError("four-frame wrapper requires the source single-position book")
    if not set(setup_names).issubset(SETUPS):
        raise ValueError("unknown setup identity")
    out = {}
    for stop_atr, max_bars in product(stop_atr_range, max_bars_range):
        result = setup_scanner(ohlcv, stop_atr=float(stop_atr), max_bars=int(max_bars), **fixed_inputs)
        for name in setup_names:
            out[(name, float(stop_atr), int(max_bars))] = (
                result[f"{name}_long_entry"], result[f"{name}_long_exit"],
                result[f"{name}_short_entry"], result[f"{name}_short_exit"])
    return _assemble(out, ["setup_identity", "setup_stop_atr", "setup_max_bars"], enable_shorting)
