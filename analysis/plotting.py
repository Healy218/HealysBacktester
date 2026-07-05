# analysis/plotting.py
import numpy as np
import vectorbt as vbt
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from typing import Optional, Union, Tuple # Import needed types
from utils.logging_utils import setup_logging
import logging
logger = setup_logging(log_file="logs/backtester.log")

# ── Light chart theme ────────────────────────────────────────────────────────
# The dashboard renders on a white background, so charts must match. Set a light
# Plotly template globally and switch vectorbt to its light theme (otherwise
# portfolio.plot() defaults to a dark template and clashes with the UI).
pio.templates.default = "plotly_white"
try:
    vbt.settings.set_theme("light")
except Exception:
    logger.warning("Could not apply vectorbt light theme; portfolio.plot() may render dark.")

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
        # This is a stacked multi-subplot figure (equity / drawdown / trades);
        # give it room so the panels don't crowd each other or their titles.
        fig.update_layout(height=620, margin=dict(t=60, b=40))
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
        fig = price_df['Close'].vbt.plot(trace_kwargs=dict(name='Close', line=dict(color='#94a3b8')))

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
        _add(rr[longs],  'Long open',  '#64748b', 'circle', entry_ts_col, entry_px_col, filled=False)
        _add(rr[shorts], 'Short open', '#64748b', 'x',      entry_ts_col, entry_px_col, filled=True)

        # --- Close markers (colored by outcome, at exit time) ---
        if exit_ts_col and exit_px_col:
            _add(rr[longs  &  win],  'Long ● (win)',   '#16a34a', 'circle', exit_ts_col, exit_px_col, filled=True)
            _add(rr[longs  & ~win],  'Long ● (loss)',  '#dc2626', 'circle', exit_ts_col, exit_px_col, filled=False)
            _add(rr[shorts &  win],  'Short ✕ (win)',  '#0d9488', 'x',      exit_ts_col, exit_px_col, filled=True)
            _add(rr[shorts & ~win],  'Short ✕ (loss)', '#f59e0b', 'x',      exit_ts_col, exit_px_col, filled=False)
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
            marker_color=np.where(pnl >= 0, '#16a34a', '#dc2626'),
            name="Trade P&L",
        ))

        # Add vertical line at zero
        fig.add_vline(x=0, line_dash="dash", line_color="#334155", opacity=0.5)

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


def plot_equity_vs_benchmark(
    portfolio: vbt.Portfolio,
    price_df: pd.DataFrame,
    column: Optional[Union[str, Tuple]] = None,
) -> Optional[go.Figure]:
    """
    Overlays the strategy equity curve against a buy-and-hold benchmark built
    with vbt.Portfolio.from_holding, using the same starting capital so the two
    curves are directly comparable.

    Args:
        portfolio: A vectorbt Portfolio object (strategy).
        price_df:  Cleaned OHLCV DataFrame with a "Close" column.
        column:    Optional column to select from a multi-column portfolio.

    Returns:
        Plotly Figure, or None on error.
    """
    if portfolio is None or price_df is None or "Close" not in price_df:
        return None
    try:
        pf = portfolio if column is None else portfolio[column]
        strat_val = pf.value()
        if strat_val is None or len(strat_val) == 0:
            return None

        # Match the benchmark's starting capital to the strategy's.
        init_cash = float(strat_val.iloc[0])
        close = price_df["Close"].reindex(strat_val.index).ffill()

        try:
            bench_pf = vbt.Portfolio.from_holding(
                close, init_cash=init_cash, freq=pf.wrapper.freq,
            )
            bench_val = bench_pf.value()
        except Exception:
            # Fallback: scale the raw price series to the same starting capital.
            bench_val = close / close.iloc[0] * init_cash

        strat_ret = (strat_val.iloc[-1] / init_cash - 1) * 100
        bench_ret = (bench_val.iloc[-1] / init_cash - 1) * 100

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=strat_val.index, y=strat_val.values, mode="lines",
            name=f"Strategy ({strat_ret:+.1f}%)", line=dict(color="#16a34a", width=2),
        ))
        fig.add_trace(go.Scatter(
            x=bench_val.index, y=bench_val.values, mode="lines",
            name=f"Buy & Hold ({bench_ret:+.1f}%)",
            line=dict(color="#0d9488", width=2, dash="dash"),
        ))
        fig.update_layout(
            title="Strategy vs Buy & Hold",
            xaxis_title="Date",
            yaxis_title="Portfolio Value ($)",
            height=420,
            margin=dict(t=60, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        return fig
    except Exception as e:
        logger.error(f"Error generating equity vs benchmark plot: {e}")
        return None


def plot_monte_carlo(
    portfolio: vbt.Portfolio,
    column: Optional[Union[str, Tuple]] = None,
    n_sims: int = 1000,
    seed: Optional[int] = 42,
) -> Optional[go.Figure]:
    """
    Monte Carlo bootstrap on the strategy's trade returns: resample the realized
    per-trade returns with replacement ``n_sims`` times, compound each resample
    into a terminal return, and plot the resulting distribution with 5th/50th/95th
    percentile confidence bands and the actually-realized return.

    Args:
        portfolio: A vectorbt Portfolio object.
        column:    Optional column to select.
        n_sims:    Number of bootstrap resamples.
        seed:      RNG seed for reproducibility (None for random).

    Returns:
        Plotly Figure, or None if there are too few trades.
    """
    if portfolio is None:
        return None
    try:
        pf = portfolio if column is None else portfolio[column]
        if pf.trades.count() < 5:
            return None  # not enough trades for a meaningful distribution

        trade_rets = np.asarray(pf.trades.returns.values, dtype=float)
        trade_rets = trade_rets[~np.isnan(trade_rets)]
        n_trades = len(trade_rets)
        if n_trades < 5:
            return None

        rng = np.random.default_rng(seed)
        sims = rng.choice(trade_rets, size=(n_sims, n_trades), replace=True)
        terminal = (np.prod(1.0 + sims, axis=1) - 1.0) * 100  # % terminal return

        p5, p50, p95 = np.percentile(terminal, [5, 50, 95])
        actual = (np.prod(1.0 + trade_rets) - 1.0) * 100

        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=terminal, nbinsx=60, marker_color="#0d9488",
            opacity=0.7, name="Simulated outcomes",
        ))
        # Draw the marker lines WITHOUT annotations (they collide when the
        # percentiles sit close together), and carry each value in the legend
        # instead — one invisible scatter per line so the number stays readable
        # regardless of how tightly the lines cluster.
        for val, color, label in [
            (p5,     "#dc2626", f"5th pct: {p5:+.1f}%"),
            (p50,    "#f59e0b", f"Median: {p50:+.1f}%"),
            (p95,    "#16a34a", f"95th pct: {p95:+.1f}%"),
            (actual, "#334155", f"Realized: {actual:+.1f}%"),
        ]:
            fig.add_vline(x=val, line_dash="dash", line_color=color)
            fig.add_trace(go.Scatter(
                x=[val], y=[None], mode="lines",
                line=dict(color=color, dash="dash", width=2),
                name=label,
            ))
        fig.update_layout(
            title=f"Monte Carlo — {n_sims:,} resamples of {n_trades} trades",
            xaxis_title="Terminal Return (%)",
            yaxis_title="Frequency",
            bargap=0.02,
            height=450,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        xanchor="right", x=1),
        )
        return fig
    except Exception as e:
        logger.error(f"Error generating Monte Carlo plot: {e}")
        return None


def plot_walkforward_folds(
    folds: list,
    init_cash: float = 100_000.0,
) -> Optional[go.Figure]:
    """
    Stitches each walk-forward fold's out-of-sample returns into one continuous
    equity curve, colouring each fold separately so the per-fold breakdown is
    visible (rather than only the last fold's curve).

    Args:
        folds: list of dicts, each {"fold": int, "param_label": str,
               "returns": pd.Series of OOS period returns}.
        init_cash: Starting capital for the stitched curve.

    Returns:
        Plotly Figure, or None if there is nothing to plot.
    """
    if not folds:
        return None
    try:
        palette = [
            "#16a34a", "#0d9488", "#f59e0b", "#dc2626", "#9b59b6",
            "#1abc9c", "#e67e22", "#2ecc71", "#e84393", "#00cec9",
        ]
        fig = go.Figure()
        equity = float(init_cash)
        plotted = False

        for i, f in enumerate(folds):
            rets = f.get("returns")
            if rets is None or len(rets) == 0:
                continue
            curve = equity * (1.0 + rets).cumprod()
            color = palette[i % len(palette)]
            fold_ret = (curve.iloc[-1] / equity - 1) * 100
            fig.add_trace(go.Scatter(
                x=curve.index, y=curve.values, mode="lines",
                name=f"Fold {f.get('fold', i + 1)} ({fold_ret:+.1f}%)",
                line=dict(color=color, width=2),
                hovertext=f"{f.get('param_label', '')}",
            ))
            # Mark the fold boundary.
            fig.add_vline(x=curve.index[0], line_dash="dot",
                          line_color="rgba(51,65,85,0.25)")
            equity = float(curve.iloc[-1])
            plotted = True

        if not plotted:
            return None

        total_ret = (equity / init_cash - 1) * 100
        fig.update_layout(
            title=f"Walk-Forward OOS Equity by Fold (total {total_ret:+.1f}%)",
            xaxis_title="Date",
            yaxis_title="Stitched OOS Equity ($)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        return fig
    except Exception as e:
        logger.error(f"Error generating walk-forward folds plot: {e}")
        return None