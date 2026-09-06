"""Four-frame adapter for AMD distribution entries and reference outcomes."""
from dataclasses import replace
from itertools import product

from signals.tv_signals import _assemble
from v3.tv_amd_po3 import AmdConfig, amd_po3


def generate_amd_po3_signals(ohlcv, compression_range, fib_extension_range,
                             enable_shorting=False, config=None, **fixed_inputs):
    base = config or AmdConfig()
    out = {}
    for compression, fib in product(compression_range, fib_extension_range):
        selected = replace(base, compression_percentile=int(compression), fib_extension=float(fib))
        result = amd_po3(ohlcv, config=selected, **fixed_inputs)
        out[(int(compression), float(fib))] = (result.long_entry, result.long_exit,
                                              result.short_entry, result.short_exit)
    return _assemble(out, ["amd_compression", "amd_fib_extension"], enable_shorting)
