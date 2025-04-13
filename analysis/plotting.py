# analysis/plotting.py
import numpy as np
import vectorbt as vbt
import pandas as pd
import plotly.graph_objects as go
from typing import Optional, Union, Tuple # Import needed types

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
    print(f"Generating portfolio summary plot figure for column: {column if column is not None else 'Default'}...")
    if portfolio is None:
        print("Error: Portfolio object is None.")
        return None
    try:
        # portfolio.plot() returns a plotly Figure object
        fig = portfolio.plot(column=column, **kwargs)
        # DO NOT call fig.show() here
        return fig # Return the figure object
    except Exception as e:
        print(f"Error generating portfolio summary plot figure: {e}")
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
    print("Generating cumulative returns plot figure...")
    if portfolio is None:
        print("Error: Portfolio object is None.")
        return None
    try:
        fig = portfolio.plot_cum_returns(benchmark_rets=benchmark_rets, column=column, **kwargs)
        # DO NOT call fig.show() here
        return fig
    except Exception as e:
        print(f"Error generating cumulative returns plot figure: {e}")
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
    print("Generating drawdowns plot figure...")
    if portfolio is None:
        print("Error: Portfolio object is None.")
        return None
    try:
        fig = portfolio.plot_drawdowns(column=column, **kwargs)
        # DO NOT call fig.show() here
        return fig
    except Exception as e:
        print(f"Error generating drawdowns plot figure: {e}")
        return None

def plot_trades(portfolio: vbt.Portfolio, price_df: pd.DataFrame, column: Optional[Union[str, Tuple]] = None, **kwargs) -> Optional[go.Figure]:
    """
    Generates the trades plotted on the price chart and returns the figure object.

    Args:
        portfolio: A vectorbt Portfolio object.
        price_df: DataFrame containing the 'Close' price series used in the backtest.
        column: Optional column name/tuple to select a specific portfolio column.
        **kwargs: Additional keyword arguments passed to portfolio.trades.plot().

    Returns:
        A plotly Figure object, or None if an error occurs.
    """
    print(f"Generating trades plot figure for column: {column if column is not None else 'Default'}...")
    if portfolio is None:
        print("Error: Portfolio object is None.")
        return None
    if price_df is None or 'Close' not in price_df.columns:
        print("Error: 'Close' column required in price_df to plot trades.")
        return None

    try:
        # Plot trades using the portfolio's trade plotter, overlaying on the close price
        fig = price_df['Close'].vbt.plot(trace_kwargs=dict(name='Close')) # Base price plot
        # Select the portfolio column if provided
        portfolio_to_plot = portfolio if column is None else portfolio[column]
        # Check if trades exist for the selected portfolio/column
        if portfolio_to_plot.trades.count() > 0:
            fig = portfolio_to_plot.trades.plot(fig=fig, **kwargs) # Add trades to the figure
        else:
            print(f"Note: No trades to plot for column {column if column is not None else 'Default'}.")
            # Return the figure with just the price plot
        # DO NOT call fig.show() here
        return fig
    except KeyError:
        print(f"Error: Column '{column}' not found in portfolio for plotting trades.")
        return None
    except Exception as e:
        print(f"Error generating trades plot figure: {e}")
        return None

# You can add more specific plotting functions as needed.