# analysis/plotting.py

import vectorbt as vbt
import pandas as pd
import plotly.graph_objects as go # Optional: For customization if needed

# Ensure plotting libraries are installed: pip install plotly kaleido nbformat
# 'kaleido' is needed for saving static images (optional)
# 'nbformat' might be needed depending on environment

def plot_portfolio_summary(portfolio: vbt.Portfolio, **kwargs):
    """
    Generates and displays vectorbt's main portfolio summary plot.

    Args:
        portfolio: A vectorbt Portfolio object.
        **kwargs: Additional keyword arguments passed to portfolio.plot().
    """
    print("Generating portfolio summary plot...")
    try:
        # portfolio.plot() returns a plotly Figure object
        fig = portfolio.plot(**kwargs)
        fig.show() # Display the figure
    except Exception as e:
        print(f"Error generating portfolio summary plot: {e}")

def plot_cumulative_returns(portfolio: vbt.Portfolio, benchmark_rets: pd.Series = None, **kwargs):
    """
    Generates and displays the cumulative returns plot.

    Args:
        portfolio: A vectorbt Portfolio object.
        benchmark_rets: Optional pandas Series of benchmark returns for comparison.
        **kwargs: Additional keyword arguments passed to plot_cum_returns().
    """
    print("Generating cumulative returns plot...")
    try:
        fig = portfolio.plot_cum_returns(benchmark_rets=benchmark_rets, **kwargs)
        fig.show()
    except Exception as e:
        print(f"Error generating cumulative returns plot: {e}")

def plot_drawdowns(portfolio: vbt.Portfolio, **kwargs):
    """
    Generates and displays the underwater (drawdown) plot.

    Args:
        portfolio: A vectorbt Portfolio object.
        **kwargs: Additional keyword arguments passed to plot_drawdowns().
    """
    print("Generating drawdowns plot...")
    try:
        fig = portfolio.plot_drawdowns(**kwargs)
        fig.show()
    except Exception as e:
        print(f"Error generating drawdowns plot: {e}")

def plot_trades(portfolio: vbt.Portfolio, price_df: pd.DataFrame, **kwargs):
    """
    Generates and displays the trades plotted on the price chart.

    Args:
        portfolio: A vectorbt Portfolio object.
        price_df: DataFrame containing the 'Close' price series used in the backtest.
        **kwargs: Additional keyword arguments passed to portfolio.trades.plot().
    """
    print("Generating trades plot...")
    if 'Close' not in price_df.columns:
        print("Error: 'Close' column required in price_df to plot trades.")
        return

    try:
        # Plot trades using the portfolio's trade plotter, overlaying on the close price
        fig = price_df['Close'].vbt.plot(trace_kwargs=dict(name='Close')) # Base price plot
        fig = portfolio.trades.plot(fig=fig, **kwargs) # Add trades to the figure
        fig.show()
    except Exception as e:
        print(f"Error generating trades plot: {e}")

# You can add more specific plotting functions as needed,
# e.g., plotting cash, assets, drawdown periods separately.