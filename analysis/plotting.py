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

def plot_parameter_heatmap(
    heatmap_df: pd.DataFrame,
    metric_name: str = "Total Return",
    x_label: str = "Parameter 2",
    y_label: str = "Parameter 1",
) -> Optional[go.Figure]:
    """
    Creates a heatmap of a metric across two parameter dimensions.

    Args:
        heatmap_df: 2D DataFrame from get_optimization_heatmap_data().
        metric_name: Label for the colorbar.
        x_label: Label for the x-axis (columns).
        y_label: Label for the y-axis (index).

    Returns:
        Plotly Figure, or None on error.
    """
    if heatmap_df is None or heatmap_df.empty:
        return None

    try:
        fig = go.Figure(data=go.Heatmap(
            z=heatmap_df.values,
            x=[str(c) for c in heatmap_df.columns],
            y=[str(i) for i in heatmap_df.index],
            colorscale="RdYlGn",
            colorbar=dict(title=metric_name),
        ))
        fig.update_layout(
            title=f"Parameter Sweep: {metric_name}",
            xaxis_title=x_label,
            yaxis_title=y_label,
        )
        return fig
    except Exception as e:
        logger.error(f"Error generating parameter heatmap: {e}")
        return None


def plot_trade_pnl_distribution(
    portfolio: vbt.Portfolio,
    column: Optional[Union[str, Tuple]] = None,
) -> Optional[go.Figure]:
    """
    Plots a histogram of trade P&L values.

    Args:
        portfolio: A vectorbt Portfolio object.
        column: Optional column to select.

    Returns:
        Plotly Figure, or None on error.
    """
    if portfolio is None:
        return None

    try:
        pf = portfolio if column is None else portfolio[column]
        if pf.trades.count() == 0:
            return None

        pnl = pf.trades.pnl.values

        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=pnl,
            nbinsx=50,
            marker_color=np.where(pnl >= 0, '#00bc8c', '#e74c3c'),
            name="Trade P&L",
        ))

        # Add vertical line at zero
        fig.add_vline(x=0, line_dash="dash", line_color="white", opacity=0.5)

        fig.update_layout(
            title="Trade P&L Distribution",
            xaxis_title="P&L ($)",
            yaxis_title="Count",
            bargap=0.05,
        )
        return fig
    except Exception as e:
        logger.error(f"Error generating P&L distribution plot: {e}")
        return None


def plot_monthly_returns(
    portfolio: vbt.Portfolio,
    column: Optional[Union[str, Tuple]] = None,
) -> Optional[go.Figure]:
    """
    Plots a monthly returns heatmap (year × month).

    Args:
        portfolio: A vectorbt Portfolio object.
        column: Optional column to select.

    Returns:
        Plotly Figure, or None on error.
    """
    if portfolio is None:
        return None

    try:
        pf = portfolio if column is None else portfolio[column]
        returns = pf.returns()

        if returns is None or returns.empty:
            return None

        # Resample to monthly returns
        monthly = returns.resample("ME").apply(lambda x: (1 + x).prod() - 1)
        monthly_df = pd.DataFrame({
            "year": monthly.index.year,
            "month": monthly.index.month,
            "return": monthly.values,
        })

        if monthly_df.empty:
            return None

        pivot = monthly_df.pivot_table(index="year", columns="month", values="return")

        month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        # Map month numbers to labels
        pivot.columns = [month_labels[m - 1] for m in pivot.columns]

        fig = go.Figure(data=go.Heatmap(
            z=pivot.values * 100,
            x=list(pivot.columns),
            y=[str(y) for y in pivot.index],
            colorscale="RdYlGn",
            colorbar=dict(title="Return %"),
            text=np.round(pivot.values * 100, 1),
            texttemplate="%{text}%",
        ))
        fig.update_layout(
            title="Monthly Returns Heatmap",
            xaxis_title="Month",
            yaxis_title="Year",
        )
        return fig
    except Exception as e:
        logger.error(f"Error generating monthly returns heatmap: {e}")
        return None