# analysis/plotting.py
import numpy as np
import vectorbt as vbt
import pandas as pd
import plotly.graph_objects as go
from typing import Optional, Union, Tuple # Import needed types
from utils.logging_utils import setup_logging
import logging
logger = setup_logging(log_file="logs/backtester.log")

# Ensure plotting libraries are installed: pip install plotly kaleido nbformat
# 'kaleido' is needed for saving static images (optional)
# 'nbformat' might be needed depending on environment


def plot_portfolio_summary(portfolio: vbt.Portfolio, column: Optional[Union[str, Tuple]] = None, **kwargs) -> Optional[go.Figure]:
    """
    Generates vectorbt's main portfolio summary plot and returns the figure object.

    Args:
        portfolio: A vectorbt Portfolio object.
        column: Optional column name/tuple to select a specific portfolio column for plotting.
        **kwargs: Additional keyword arguments passed to portfolio.plot().

    Returns:
        A plotly Figure object, or None if an error occurs.
    """
    logger.info(f"Generating portfolio summary plot figure for column: {column if column is not None else 'Default'}...")
    if portfolio is None:
        logger.error("Error: Portfolio object is None.")
        return None
    try:
        # portfolio.plot() returns a plotly Figure object
        fig = portfolio.plot(column=column, **kwargs)
        # DO NOT call fig.show() here
        return fig # Return the figure object
    except Exception as e:
        logger.error(f"Error generating portfolio summary plot figure: {e}")
        return None

def plot_cumulative_returns(portfolio: vbt.Portfolio, benchmark_rets: Optional[pd.Series] = None, column: Optional[Union[str, Tuple]] = None, **kwargs) -> Optional[go.Figure]:
    """
    Generates the cumulative returns plot and returns the figure object.

    Args:
        portfolio: A vectorbt Portfolio object.
        benchmark_rets: Optional pandas Series of benchmark returns for comparison.
        column: Optional column name/tuple to select a specific portfolio column.
        **kwargs: Additional keyword arguments passed to plot_cum_returns().

    Returns:
        A plotly Figure object, or None if an error occurs.
    """
    logger.info("Generating cumulative returns plot figure...")
    if portfolio is None:
        logger.error("Error: Portfolio object is None.")
        return None
    try:
        fig = portfolio.plot_cum_returns(benchmark_rets=benchmark_rets, column=column, **kwargs)
        # DO NOT call fig.show() here
        return fig
    except Exception as e:
        logger.error(f"Error generating cumulative returns plot figure: {e}")
        return None

def plot_drawdowns(portfolio: vbt.Portfolio, column: Optional[Union[str, Tuple]] = None, **kwargs) -> Optional[go.Figure]:
    """
    Generates the underwater (drawdown) plot and returns the figure object.

    Args:
        portfolio: A vectorbt Portfolio object.
        column: Optional column name/tuple to select a specific portfolio column.
        **kwargs: Additional keyword arguments passed to plot_drawdowns().

    Returns:
        A plotly Figure object, or None if an error occurs.
    """
    logger.info("Generating drawdowns plot figure...")
    if portfolio is None:
        logger.error("Error: Portfolio object is None.")
        return None
    try:
        fig = portfolio.plot_drawdowns(column=column, **kwargs)
        # DO NOT call fig.show() here
        return fig
    except Exception as e:
        logger.error(f"Error generating drawdowns plot figure: {e}")
        return None

def plot_trades(portfolio: vbt.Portfolio, price_df: pd.DataFrame, column: Optional[Union[str, Tuple]] = None, **kwargs) -> Optional[go.Figure]:
    """
    Plots trades as entry-point markers on the price chart.

    For reversal-based strategies (long → short → long), entry and exit events
    happen at the same bar and price, so plotting both causes one marker to
    cover the other entirely.  Showing only entry markers avoids this overlap:
    the end of one trade is implied by the start of the next.

    Marker key
    ----------
    Open markers  (at entry):
      Long open   — gray   outline circle ●
      Short open  — gray   x              ✕

    Close markers (at exit, colored by outcome):
      Long  (win)  — green  filled circle  ●
      Long  (loss) — red    outline circle ●
      Short (win)  — teal   filled x       ✕
      Short (loss) — orange outline x      ✕
    """
    logger.info(f"Generating trades plot figure for column: {column if column is not None else 'Default'}...")
    if portfolio is None:
        logger.error("Error: Portfolio object is None.")
        return None
    if price_df is None or 'Close' not in price_df.columns:
        logger.error("Error: 'Close' column required in price_df to plot trades.")
        return None

    try:
        fig = price_df['Close'].vbt.plot(trace_kwargs=dict(name='Close', line=dict(color='#aaaaaa')))

        pf = portfolio if column is None else portfolio[column]
        if pf.trades.count() == 0:
            logger.info("No trades to plot.")
            return fig

        rr = pf.trades.records_readable

        # Locate timestamp and price columns (names vary slightly by vbt version)
        entry_ts_col = next((c for c in rr.columns if 'entry' in c.lower() and 'time'  in c.lower()), None)
        entry_px_col = next((c for c in rr.columns if 'entry' in c.lower() and 'price' in c.lower()), None)
        exit_ts_col  = next((c for c in rr.columns if 'exit'  in c.lower() and 'time'  in c.lower()), None)
        exit_px_col  = next((c for c in rr.columns if 'exit'  in c.lower() and 'price' in c.lower()), None)

        if not all([entry_ts_col, entry_px_col]):
            logger.warning("Could not locate entry columns; falling back to default trades.plot()")
            return pf.trades.plot(fig=fig)

        # Determine win/loss for each trade
        pnl_col = next((c for c in rr.columns if 'pnl' in c.lower()), None)
        if pnl_col:
            win = rr[pnl_col] >= 0
        else:
            ret_col = next((c for c in rr.columns if 'return' in c.lower()), None)
            win = rr[ret_col] >= 0 if ret_col else pd.Series(True, index=rr.index)

        longs  = rr['Direction'] == 'Long'
        shorts = rr['Direction'] == 'Short'

        def _add(df, name, color, symbol, x_col, y_col, filled=True):
            if df.empty:
                return
            marker = dict(symbol=symbol, color=color, size=9,
                          line=dict(color=color, width=2))
            if not filled:
                marker['color'] = 'rgba(0,0,0,0)'
            fig.add_trace(go.Scatter(
                x=df[x_col], y=df[y_col],
                mode='markers', marker=marker, name=name,
            ))

        # --- Open markers (neutral, at entry time) ---
        _add(rr[longs],  'Long open',  '#888888', 'circle', entry_ts_col, entry_px_col, filled=False)
        _add(rr[shorts], 'Short open', '#888888', 'x',      entry_ts_col, entry_px_col, filled=True)

        # --- Close markers (colored by outcome, at exit time) ---
        if exit_ts_col and exit_px_col:
            _add(rr[longs  &  win],  'Long ● (win)',   '#00bc8c', 'circle', exit_ts_col, exit_px_col, filled=True)
            _add(rr[longs  & ~win],  'Long ● (loss)',  '#e74c3c', 'circle', exit_ts_col, exit_px_col, filled=False)
            _add(rr[shorts &  win],  'Short ✕ (win)',  '#3498db', 'x',      exit_ts_col, exit_px_col, filled=True)
            _add(rr[shorts & ~win],  'Short ✕ (loss)', '#f39c12', 'x',      exit_ts_col, exit_px_col, filled=False)
        else:
            logger.warning("Could not locate exit columns; close markers skipped.")

        fig.update_layout(
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        )
        return fig

    except KeyError:
        logger.error(f"Error: Column '{column}' not found in portfolio for plotting trades.")
        return None
    except Exception as e:
        logger.error(f"Error generating trades plot figure: {e}")
        return None

# You can add more specific plotting functions as needed.