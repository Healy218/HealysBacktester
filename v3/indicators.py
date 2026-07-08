# v3/indicators.py — Stage 3: TV-validated indicator library.
"""Curated 'modern' indicators ported from public Pine source, vectorized
(numpy/numba). Candidates: Squeeze Momentum, SuperTrend, anchored VWAP,
Keltner squeeze, ADX regime filter, Ichimoku, OBV/volume-profile features,
RSI/MACD divergences — final list decided here.

Correctness harness: every indicator unit-tested against TradingView's
plotted values on a pinned SPY window (export TV values once, freeze as
fixtures in tests/). No indicator enters the feature set without passing.
All features computed strictly from past bars (v2 leak discipline)."""
