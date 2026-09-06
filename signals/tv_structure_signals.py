"""Offline proposal adapters; external numerical parity gates remain pending.

Enter on the author's confirmed MSB/channel-break event and exit on the
opposite event. Opposite-event exits are our proposal rules, not upstream
strategy accounting. These adapters are not registered in live configuration.
"""
from itertools import product

from signals.tv_signals import _assemble
from v3.tv_market_structure import market_structure_break
from v3.tv_sr_channels import support_resistance_channels


def generate_market_structure_signals(ohlcv, zigzag_range, fib_factor_range,
                                      enable_shorting=False):
    results = {}
    for length, factor in product(zigzag_range, fib_factor_range):
        frame = market_structure_break(ohlcv, zigzag_length=length, fib_factor=factor)
        results[(length, factor)] = (frame.bull_signal, frame.bear_signal, frame.bear_signal, frame.bull_signal)
    return _assemble(results, ["msb_zigzag_length", "msb_fib_factor"], enable_shorting)


def generate_sr_channel_signals(ohlcv, pivot_range, width_range, enable_shorting=False, **fixed_inputs):
    results = {}
    for period, width in product(pivot_range, width_range):
        frame = support_resistance_channels(ohlcv, pivot_period=period,
                                            channel_width_pct=width, **fixed_inputs)
        results[(period, width)] = (frame.bull_signal, frame.bear_signal, frame.bear_signal, frame.bull_signal)
    return _assemble(results, ["sr_pivot_period", "sr_channel_width"], enable_shorting)
