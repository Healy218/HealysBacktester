"""Proposal adapters for the isolated TradingView trend implementations.

Gaussian/Uptrick: enter on the author's directional alert; exit on the opposite
alert. Fibonacci: enter on continuation alerts; exit on a trend reversal. The
exit rules are our explicit proposal contract, not claims about an upstream
strategy backtest. No upstream simulated account statistics enter these frames.
"""
from __future__ import annotations

from itertools import product

from signals.tv_signals import _assemble
from v3 import tv_trend_indicators as ta


def generate_gaussian_filter_signals(
    ohlcv, length_range, poles_range, enable_shorting=False, **fixed_inputs,
):
    out = {}
    for length, poles in product(length_range, poles_range):
        result = ta.gaussian_filter_trend(ohlcv, length=int(length), poles=int(poles), **fixed_inputs)
        bull, bear = result.bull_signal, result.bear_signal
        out[(int(length), int(poles))] = bull, bear, bear, bull
    return _assemble(out, ["gaussian_length", "gaussian_poles"], enable_shorting)


def generate_fibonacci_trend_signals(
    ohlcv, midline_range, pivot_range, bandwidth_range, enable_shorting=False,
    **fixed_inputs,
):
    out = {}
    for midline, pivot, width in product(midline_range, pivot_range, bandwidth_range):
        result = ta.fibonacci_trend_continuation(
            ohlcv, midline_length=int(midline), pivot_length=int(pivot),
            band_width=float(width), **fixed_inputs)
        out[(int(midline), int(pivot), float(width))] = (
            result.bull_signal, result.bear_flip, result.bear_signal, result.bull_flip)
    return _assemble(out, ["fib_midline", "fib_pivot", "fib_bandwidth"], enable_shorting)


def generate_uptrick_trend_signals(
    ohlcv, trend_range, sensitivity_range, enable_shorting=False, **fixed_inputs,
):
    out = {}
    for length, sensitivity in product(trend_range, sensitivity_range):
        result = ta.uptrick_adaptive_trend(
            ohlcv, trend_length=int(length), sensitivity=float(sensitivity), **fixed_inputs)
        bull, bear = result.bull_signal, result.bear_signal
        out[(int(length), float(sensitivity))] = bull, bear, bear, bull
    return _assemble(out, ["up_trend_length", "up_sensitivity"], enable_shorting)
