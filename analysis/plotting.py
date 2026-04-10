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
    Generates the trades plotted on the price chart and returns the figure object.
    Long entries/exits and short entries/exits are drawn with distinct markers and
    colors so it is visually clear which direction each trade is.

    Long Entry  — green  triangle-up
    Long Exit   — green  triangle-down (win) / red triangle-down (loss)
    Short Entry — red    triangle-down  (selling short)
    Short Exit  — orange triangle-up    (covering)
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

        # Identify entry and exit timestamps — column name varies by vbt version
        entry_ts_col = next((c for c in rr.columns if 'entry' in c.lower() and 'time' in c.lower()), None)
        exit_ts_col  = next((c for c in rr.columns if 'exit'  in c.lower() and 'time' in c.lower()), None)
        entry_px_col = next((c for c in rr.columns if 'entry' in c.lower() and 'price' in c.lower()), None)
        exit_px_col  = next((c for c in rr.columns if 'exit'  in c.lower() and 'price' in c.lower()), None)

        if not all([entry_ts_col, exit_ts_col, entry_px_col, exit_px_col]):
            # Fall back to the default vectorbt plot if column names don't match
            logger.warning("Could not locate entry/exit columns; falling back to default trades.plot()")
            return pf.trades.plot(fig=fig)

        long_trades  = rr[rr['Direction'] == 'Long']
        short_trades = rr[rr['Direction'] == 'Short']
        closed_exits = rr[rr['Status'] == 'Closed']
        long_closed  = closed_exits[closed_exits['Direction'] == 'Long']
        short_closed = closed_exits[closed_exits['Direction'] == 'Short']

        def _add_scatter(df, ts_col, px_col, name, color, symbol, size=10):
            if df.empty:
                return
            fig.add_trace(go.Scatter(
                x=df[ts_col], y=df[px_col],
                mode='markers',
                marker=dict(symbol=symbol, color=color, size=size,
                            line=dict(color='white', width=1)),
                name=name,
            ))

        _add_scatter(long_trades,  entry_ts_col, entry_px_col, 'Long Entry',  '#00bc8c', 'triangle-up')
        _add_scatter(long_closed,  exit_ts_col,  exit_px_col,  'Long Exit',   '#3498db', 'triangle-down')
        _add_scatter(short_trades, entry_ts_col, entry_px_col, 'Short Entry', '#e74c3c', 'triangle-down')
        _add_scatter(short_closed, exit_ts_col,  exit_px_col,  'Short Cover', '#f39c12', 'triangle-up')

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