# options/analysis/options_plotting.py
"""
Options-specific plotting.

Complements analysis/plotting.py (equity, trades, Monte Carlo, …) with charts
that only make sense for options. Figures use the same light template + green/
teal palette as the dashboard. Kept intentionally small for now — payoff at
expiry plus the contract's own price path; greeks-over-time lands with the
history-capable data source.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

# Palette shared with the dashboard / analysis.plotting
_GREEN, _TEAL, _RED, _SLATE = "#16a34a", "#0d9488", "#dc2626", "#334155"


def plot_payoff_at_expiry(
    strike: float,
    premium: float,
    right: str = "C",
    spot_range: Optional[tuple[float, float]] = None,
    n: int = 201,
) -> go.Figure:
    """Long single-leg payoff at expiration (per share, before the ×100 multiplier).

    Args:
        strike:  Option strike.
        premium: Price paid per share (the option's entry price).
        right:   "C" for a long call, "P" for a long put.
        spot_range: (min, max) underlying prices to plot; defaults to ±30% of strike.
        n: Number of points along the underlying axis.
    """
    r = right.upper()[:1]
    lo, hi = spot_range or (strike * 0.7, strike * 1.3)
    spots = np.linspace(lo, hi, n)
    intrinsic = np.maximum(spots - strike, 0.0) if r == "C" else np.maximum(strike - spots, 0.0)
    pnl = intrinsic - premium
    breakeven = strike + premium if r == "C" else strike - premium

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=spots, y=pnl, mode="lines", name="P&L at expiry",
        line=dict(color=_GREEN, width=2),
    ))
    fig.add_hline(y=0, line_dash="dash", line_color=_SLATE, opacity=0.5)
    fig.add_vline(x=breakeven, line_dash="dot", line_color=_TEAL,
                  annotation_text=f"Breakeven {breakeven:.2f}", annotation_position="top")
    fig.add_vline(x=strike, line_dash="dot", line_color=_SLATE, opacity=0.4,
                  annotation_text=f"Strike {strike:g}", annotation_position="bottom")
    fig.update_layout(
        template="plotly_white",
        title=f"Long {'Call' if r == 'C' else 'Put'} Payoff at Expiry "
              f"(strike {strike:g}, premium {premium:.2f})",
        xaxis_title="Underlying price at expiry",
        yaxis_title="P&L per share ($)",
    )
    return fig


def plot_contract_price(opt_df: pd.DataFrame, title: str = "Option Contract Price") -> Optional[go.Figure]:
    """Plot a single contract's close price over its life."""
    if opt_df is None or opt_df.empty or "Close" not in opt_df.columns:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=opt_df.index, y=opt_df["Close"], mode="lines",
        name="Contract close", line=dict(color=_TEAL, width=2),
    ))
    fig.update_layout(
        template="plotly_white", title=title,
        xaxis_title="Date", yaxis_title="Option price ($)",
    )
    return fig
