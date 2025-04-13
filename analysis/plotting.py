# analysis/plotting.py

import vectorbt as vbt
import pandas as pd
import plotly.graph_objects as go # Optional: For customization if needed

# Ensure plotting libraries are installed: pip install plotly kaleido nbformat
# 'kaleido' is needed for saving static images (optional)
# 'nbformat' might be needed depending on environment

def plot_portfolio_summary(portfolio: vbt.Portfolio, column=None, **kwargs): # Added column=None
    """
    Generates and displays vectorbt's main portfolio summary plot.

    Args:
        portfolio: A vectorbt Portfolio object.
        column: The specific column (parameter set) to plot. If None, plots default (might error on multi-column).
        **kwargs: Additional keyword arguments passed to portfolio.plot().
    """
    # Updated print statement
    print(f"Generating portfolio summary plot for column: {'Default' if column is None else column}...")
    try:
        # Pass the column argument to the underlying plot function
        fig = portfolio.plot(column=column, **kwargs)
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

def plot_trades(portfolio: vbt.Portfolio, price_df: pd.DataFrame, column=None, **kwargs): # Added column=None
    """
    Generates and displays the trades plotted on the price chart for a specific column.

    Args:
        portfolio: A vectorbt Portfolio object.
        price_df: DataFrame containing the 'Close' price series used in the backtest.
        column: The specific column (parameter set) whose trades to plot.
        **kwargs: Additional keyword arguments passed to portfolio.trades.plot().
    """
    # Updated print statement
    print(f"Generating trades plot for column: {'Default' if column is None else column}...")
    if 'Close' not in price_df.columns:
        print("Error: 'Close' column required in price_df to plot trades.")
        return

    try:
        fig = price_df['Close'].vbt.plot(trace_kwargs=dict(name='Close')) # Base price plot

        # Select the portfolio column BEFORE accessing trades if a column is specified
        portfolio_to_plot = portfolio if column is None else portfolio[column]

        # Plot trades using the selected portfolio/column's trade plotter
        fig = portfolio_to_plot.trades.plot(fig=fig, **kwargs)
        fig.show()
    except Exception as e:
        print(f"Error generating trades plot: {e}")


# You can add more specific plotting functions as needed,
# e.g., plotting cash, assets, drawdown periods separately.