# main.py — Healy's Backtester Interactive Dashboard
#
# Tab 1: Run a backtest live — pick ticker, dates, interval, strategy → top-5 results + graphs.
# Tab 2: Browse previously saved backtest result directories.
#
# Run from the project root:  python main.py
# Then open:  http://127.0.0.1:8050

import os
import glob
import json
import shutil
import threading
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, ctx, no_update

# Load .env so ALPACA_API_KEY etc. are available before anything tries to use them
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — rely on environment variables being set manually

# ── Project module imports ──────────────────────────────────────────────────
from utils.logging_utils import setup_logging
from utils import config_parser
from analysis import plotting
from backtests import run_ma, run_rsi, run_macd, run_volume, run_bbands, run_stoch, run_elliott, run_sentiment, run_walkforward
from options.backtests import run_options_single, signal_overlay

logger = setup_logging(log_file="logs/backtester.log")

# ── Constants ───────────────────────────────────────────────────────────────
RESULTS_DIR          = "results"
CONFIG_FILENAME      = "config_used.py"
BEST_STATS_FILENAME  = "best_params_stats.csv"
TRADES_FILENAME      = "best_params_trades.csv"
SUMMARY_PLOT_FILE    = "plot_portfolio_summary.json"
TRADES_PLOT_FILE     = "plot_trades.json"

STRATEGIES = {
    "MA Crossover":         {"runner": run_ma,     "config_key": "STRATEGY_MA_CROSSOVER"},
    "RSI Threshold":        {"runner": run_rsi,    "config_key": "STRATEGY_RSI"},
    "MACD Crossover":       {"runner": run_macd,   "config_key": "STRATEGY_MACD"},
    "Volume Breakout":      {"runner": run_volume, "config_key": "STRATEGY_VOLUME_BREAKOUT"},
    "Bollinger Bands":      {"runner": run_bbands, "config_key": "STRATEGY_BBANDS"},
    "Stochastic Crossover": {"runner": run_stoch,   "config_key": "STRATEGY_STOCH"},
    "Elliott Wave / Fib":   {"runner": run_elliott, "config_key": "STRATEGY_ELLIOTT"},
    "Sentiment":            {"runner": run_sentiment, "config_key": "STRATEGY_SENTIMENT"},
    "Options (Single-Leg)": {"runner": run_options_single, "config_key": "STRATEGY_OPTIONS_SINGLE"},
}

# Strategies that trade a single instrument per signal (no parameter grid) and so
# cannot be walk-forward optimized.
NO_WALKFORWARD = {"Options (Single-Leg)"}

INTERVALS = [
    {"label": "1 Minute",  "value": "1m"},
    {"label": "5 Minutes", "value": "5m"},
    {"label": "15 Minutes", "value": "15m"},
    {"label": "1 Hour", "value": "1h"},
    {"label": "1 Day", "value": "1D"},
]

# ── In-memory state ──────────────────────────────────────────────────────────
# _last_run: keyed by symbol, stores portfolio/price_data objects (not JSON-safe)
_last_run: dict = {"by_symbol": {}}

# _run_state: shared between the worker thread and the interval callback
_run_state: dict = {
    "running":  False,
    "pct":      0,
    "step":     "",
    "result":   None,   # dict with all_best_rows + errors when worker finishes
    "consumed": True,   # True once the interval has read and displayed the result
}
_run_lock = threading.Lock()


def _set_progress(pct: int, step: str) -> None:
    """Thread-safe progress update called from the worker thread."""
    with _run_lock:
        _run_state["pct"]  = pct
        _run_state["step"] = step
    logger.info(f"[Progress {pct:3d}%] {step}")


def _worker(tickers, start, end, interval, strategy, backtest_config, strategy_config,
            use_walkforward=False, asset_type="stock", options_exec_config=None):
    """
    Background thread: runs the full backtest for every ticker, writing progress
    updates to _run_state so the Dash interval callback can display them.
    """
    try:
        _set_progress(5, "Configuration loaded")
        runner = STRATEGIES[strategy]["runner"]
        # Options asset type: execute the strategy's signals as option orders
        # (calls on longs, puts on shorts). The single-leg strategy is already
        # options-native, so it never gets wrapped.
        if asset_type == "options" and runner is not run_options_single:
            runner = signal_overlay.wrap(runner, options_exec_config or {})
        _last_run["by_symbol"] = {}
        all_best_rows = []
        errors        = []
        n             = len(tickers)

        for i, sym in enumerate(tickers):
            # Each ticker gets an equal slice of the 10 → 95 % range
            base  = 10 + i * 85 // n
            chunk = 85 // n

            _set_progress(base, f"[{sym}] Loading data and generating signals…")

            # Build a progress callback so the chunked simulator can update the bar
            def _make_chunk_cb(sym_name, pct_base, pct_range):
                def _cb(chunk_idx, n_chunks):
                    frac = (chunk_idx + 1) / max(n_chunks, 1)
                    pct = pct_base + int(frac * pct_range)
                    _set_progress(pct, f"[{sym_name}] Simulating chunk {chunk_idx + 1}/{n_chunks}…")
                return _cb

            chunk_cb = _make_chunk_cb(sym, base, chunk * 8 // 10)

            try:
                if use_walkforward:
                    result = run_walkforward.run(
                        sym, start, end, interval, backtest_config, strategy_config,
                        progress_callback=chunk_cb,
                        inner_strategy=strategy,
                        inner_strategy_config=strategy_config,
                    )
                else:
                    result = runner.run(
                        sym, start, end, interval, backtest_config, strategy_config,
                        progress_callback=chunk_cb,
                    )
            except Exception as exc:
                logger.exception(f"[{sym}] Unhandled exception in runner: {exc}")
                errors.append(f"{sym}: {exc}")
                _last_run["by_symbol"][sym] = {"portfolio": None, "price_data": None}
                _set_progress(base + chunk, f"[{sym}] Failed")
                continue

            _set_progress(base + chunk * 9 // 10, f"[{sym}] Ranking results…")

            _last_run["by_symbol"][sym] = {
                "portfolio":     result.pop("portfolio",     None),
                "price_data":    result.pop("price_data",    None),
                "wf_folds":      result.pop("wf_folds",      None),
                "option_series": result.pop("option_series", None),
            }
            result.pop("option_blotter", None)   # not JSON-needed by the table

            if result.get("error"):
                errors.append(f"{sym}: {result['error']}")
                _set_progress(base + chunk, f"[{sym}] Error")
                continue

            top5 = result.get("top5", [])
            if not top5:
                errors.append(f"{sym}: no results returned")
                _set_progress(base + chunk, f"[{sym}] No results")
                continue

            # Calculate buy-and-hold benchmark return for this ticker
            sym_price = _last_run["by_symbol"][sym].get("price_data")
            if sym_price is not None and not sym_price.empty:
                bm_return = (sym_price["Close"].iloc[-1] / sym_price["Close"].iloc[0] - 1) * 100
                bm_return = round(float(bm_return), 2)
            else:
                bm_return = None

            for row in top5:
                r = row.copy()
                r["symbol"] = sym
                r["benchmark_return_pct"] = bm_return
                all_best_rows.append(r)

            _set_progress(base + chunk, f"[{sym}] Done")

        _set_progress(98, "Finalizing…")

        for i, row in enumerate(all_best_rows, start=1):
            row["rank"] = i

        with _run_lock:
            _run_state["result"]   = {"all_best_rows": all_best_rows, "errors": errors}
            _run_state["pct"]      = 100
            _run_state["step"]     = "Complete"
            _run_state["running"]  = False
            _run_state["consumed"] = False

    except Exception as e:
        logger.exception(f"Worker thread unexpected error: {e}")
        with _run_lock:
            _run_state["result"]   = {"all_best_rows": [], "errors": [str(e)]}
            _run_state["pct"]      = 100
            _run_state["step"]     = f"Error: {e}"
            _run_state["running"]  = False
            _run_state["consumed"] = False


# ── App ─────────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    title="Healy Labs BT",
)

# ── Helper functions ─────────────────────────────────────────────────────────

CACHE_DIR = "data/cache"


def _get_cache_info() -> tuple[int, str]:
    """Returns (file_count, human_readable_size) for the data cache directory."""
    try:
        if not os.path.isdir(CACHE_DIR):
            return 0, "0 B"
        files = glob.glob(os.path.join(CACHE_DIR, "*.csv"))
        total_bytes = sum(os.path.getsize(f) for f in files)
        count = len(files)
        if total_bytes < 1024:
            size_str = f"{total_bytes} B"
        elif total_bytes < 1024 ** 2:
            size_str = f"{total_bytes / 1024:.1f} KB"
        elif total_bytes < 1024 ** 3:
            size_str = f"{total_bytes / 1024**2:.1f} MB"
        else:
            size_str = f"{total_bytes / 1024**3:.2f} GB"
        return count, size_str
    except Exception:
        return 0, "?"


def _get_available_results(base_dir: str) -> list[dict]:
    runs = []
    try:
        if os.path.isdir(base_dir):
            for item in sorted(os.listdir(base_dir), reverse=True):
                if os.path.isdir(os.path.join(base_dir, item)):
                    runs.append({"label": item, "value": item})
    except Exception:
        pass
    return runs


def _fmt_pct(val) -> str:
    if val is None:
        return "N/A"
    try:
        return f"{float(val):.2f}%"
    except (TypeError, ValueError):
        return str(val)


def _fmt_num(val, decimals=2) -> str:
    if val is None:
        return "N/A"
    try:
        return f"{float(val):.{decimals}f}"
    except (TypeError, ValueError):
        return str(val)


def _load_config_file(run_dir: str) -> str:
    path = os.path.join(run_dir, CONFIG_FILENAME)
    try:
        if os.path.exists(path):
            return Path(path).read_text()
        return "Config file not found."
    except Exception as e:
        return f"Error: {e}"


def _load_csv(run_dir: str, filename: str) -> "pd.DataFrame | pd.Series | None":
    path = os.path.join(run_dir, filename)
    try:
        if os.path.exists(path):
            df = pd.read_csv(path, index_col=0)
            if isinstance(df, pd.DataFrame) and df.shape[1] == 1:
                return df.iloc[:, 0]
            return df
    except Exception:
        pass
    return None


def _load_fig(run_dir: str, filename: str) -> "go.Figure | None":
    path = os.path.join(run_dir, filename)
    try:
        if os.path.exists(path):
            with open(path) as f:
                return pio.from_json(json.dumps(json.load(f)))
    except Exception:
        pass
    return None


def _make_stats_table(data):
    if data is None:
        return html.P("Stats not found.")
    if isinstance(data, pd.Series):
        df = data.reset_index()
        df.columns = ["Metric", "Value"]
    elif isinstance(data, pd.DataFrame):
        df = data.reset_index()
    else:
        return html.P("Could not parse stats.")
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].apply(lambda x: f"{x:,.3f}" if pd.notna(x) else x)
    return dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in df.columns],
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left", "padding": "4px 8px",
                    "backgroundColor": "#ffffff", "color": "#1e293b",
                    "border": "1px solid #eef2f1"},
        style_header={"backgroundColor": "#16a34a", "color": "white", "fontWeight": "bold"},
    )


def _make_trades_table(data):
    if data is None or (isinstance(data, pd.DataFrame) and data.empty):
        return html.P("No trade records found.")
    if isinstance(data, pd.Series):
        data = data.to_frame()
    return dash_table.DataTable(
        data=data.reset_index(drop=True).to_dict("records"),
        columns=[{"name": c, "id": c} for c in data.columns],
        page_size=15,
        style_table={"overflowX": "auto"},
        style_cell={"minWidth": "80px", "maxWidth": "160px",
                    "overflow": "hidden", "textOverflow": "ellipsis",
                    "backgroundColor": "#ffffff", "color": "#1e293b",
                    "border": "1px solid #eef2f1"},
        style_header={"backgroundColor": "#16a34a", "color": "white", "fontWeight": "bold"},
    )


def _build_table_data(all_best_rows):
    """Convert all_best_rows into the col_defs + table_rows the DataTable needs."""
    # Detect walk-forward mode by checking for WF-specific fields
    is_wf = any(row.get("is_sharpe") is not None for row in all_best_rows)

    col_defs = [
        {"name": "Symbol",       "id": "symbol"},
        {"name": "Ranked By",    "id": "ranked_by"},
        {"name": "Parameters",   "id": "param_label"},
        {"name": "Return %",     "id": "total_return_pct"},
        {"name": "Benchmark %",  "id": "benchmark_return_pct"},
        {"name": "Sharpe",       "id": "sharpe_ratio"},
        {"name": "Max DD %",     "id": "max_drawdown_pct"},
        {"name": "Win Rate %",   "id": "win_rate_pct"},
        {"name": "Best Trade %", "id": "best_trade_pct"},
        {"name": "# Trades",     "id": "total_trades"},
    ]
    if is_wf:
        col_defs.extend([
            {"name": "IS Sharpe",   "id": "is_sharpe"},
            {"name": "IS Return %", "id": "is_return_pct"},
        ])

    table_rows = []
    for row in all_best_rows:
        tr = {
            "symbol":               row["symbol"],
            "ranked_by":            row.get("ranked_by", ""),
            "param_label":          row["param_label"],
            "total_return_pct":     _fmt_pct(row.get("total_return_pct")),
            "benchmark_return_pct": _fmt_pct(row.get("benchmark_return_pct")),
            "sharpe_ratio":         _fmt_num(row.get("sharpe_ratio"), 3),
            "max_drawdown_pct":     _fmt_pct(row.get("max_drawdown_pct")),
            "win_rate_pct":         _fmt_pct(row.get("win_rate_pct")),
            "best_trade_pct":       _fmt_pct(row.get("best_trade_pct")),
            "total_trades":         row.get("total_trades", 0),
        }
        if is_wf:
            tr["is_sharpe"] = _fmt_num(row.get("is_sharpe"), 3)
            tr["is_return_pct"] = _fmt_pct(row.get("is_return_pct"))
        table_rows.append(tr)
    return col_defs, table_rows


# ═══════════════════════════════════════════════════════════════════════════
#  LAYOUT
# ═══════════════════════════════════════════════════════════════════════════

def _graph_card(graph_id: str, className: str = "mb-3"):
    """Wrap a responsive dcc.Graph in a card for a consistent, tidy chart look.

    ``responsive=True`` (plus the clientside resize on chart-tab switch) ensures
    charts that first render inside a hidden sub-tab expand to full width once
    their tab becomes visible.
    """
    return dbc.Card(
        dbc.CardBody(
            dcc.Graph(id=graph_id, responsive=True, config={"displaylogo": False}),
        ),
        className=f"chart-card {className}",
    )


def _kpi_card(label: str, value: str, tone: str = "neutral", sub: str | None = None):
    """A single hero metric card. ``tone`` ∈ {pos, neg, warn, neutral} colors the value."""
    return dbc.Col(
        dbc.Card(dbc.CardBody([
            html.Div(label, className="kpi-label"),
            html.Div(value, className=f"kpi-value kpi-{tone}"),
            html.Div(sub or " ", className="kpi-sub"),
        ]), className="kpi-card h-100"),
        xs=6, md=True,
    )


def _control_row():
    """The top input bar for Tab 1."""
    today      = date.today()
    one_yr_ago = today - timedelta(days=365)
    return dbc.Card(dbc.CardBody(dbc.Row([

        dbc.Col([
            dbc.Label("Tickers (comma-separated)"),
            dbc.Input(id="ticker-input", placeholder="e.g. SPY, QQQ, AAPL", type="text",
                      value="SPY", debounce=False),
        ], xs=12, sm=6, md=2),

        dbc.Col([
            dbc.Label("Start Date"),
            dbc.Input(id="start-date", type="date",
                      value=one_yr_ago.isoformat(), min="2000-01-01"),
        ], xs=12, sm=6, md=2),

        dbc.Col([
            dbc.Label("End Date"),
            dbc.Input(id="end-date", type="date",
                      value=today.isoformat(), min="2000-01-01"),
        ], xs=12, sm=6, md=2),

        dbc.Col([
            dbc.Label("Interval"),
            dcc.Dropdown(
                id="interval-dd",
                options=INTERVALS,
                value="1D",
                clearable=False,
            ),
        ], xs=12, sm=6, md=2),

        dbc.Col([
            dbc.Label("Strategy"),
            dcc.Dropdown(
                id="strategy-dd",
                options=[{"label": k, "value": k} for k in STRATEGIES],
                value="MA Crossover",
                clearable=False,
            ),
        ], xs=12, sm=6, md=2),

        dbc.Col([
            dbc.Label("Asset Type"),
            dcc.Dropdown(
                id="asset-type-dd",
                options=[
                    {"label": "Stocks", "value": "stock"},
                    {"label": "Options (calls/puts)", "value": "options"},
                ],
                value="stock",
                clearable=False,
            ),
        ], xs=12, sm=6, md=2),

        dbc.Col([
            dbc.Label("\u00a0"),   # non-breaking space to align button
            dbc.Button(
                "▶  Run Backtest", id="run-btn", color="success",
                className="w-100",
            ),
        ], xs=12, sm=6, md=1),

        dbc.Col([
            dbc.Label("\u00a0"),
            dbc.Checklist(
                id="wf-toggle",
                options=[{"label": " Walk-Forward", "value": "wf"}],
                value=[],
                inline=True,
                className="mt-2",
                style={"fontSize": "0.85rem"},
            ),
        ], xs=12, sm=6, md=1),

    ], align="end", className="g-3")), className="mb-3")


def _cache_row():
    """Cache management bar below the control row."""
    count, size = _get_cache_info()
    return dbc.Card(dbc.CardBody(dbc.Row([
        dbc.Col([
            html.Span(
                f"Cache: {count} files ({size})",
                id="cache-info",
                style={"color": "#64748b", "fontSize": "0.85rem", "fontFamily": "monospace"},
            ),
        ], xs=12, sm=6, md=4, className="d-flex align-items-center"),
        dbc.Col([
            dbc.Button(
                "Clear Cache", id="clear-cache-btn", color="danger", outline=True,
                size="sm",
            ),
        ], xs=12, sm=6, md=2),
        dbc.Col([
            dbc.Alert(
                id="cache-alert", is_open=False, color="info",
                className="mb-0 py-1 px-2",
                style={"fontSize": "0.85rem"},
            ),
        ], xs=12, md=6, className="d-flex align-items-center"),
    ], align="center", className="g-2")), className="mb-3")


def _results_tab():
    return [
        # ── Collapsible controls ──────────────────────────────────────────────
        dbc.Row([
            dbc.Col(html.Span("Backtest Controls", className="section-label"),
                    width="auto"),
            dbc.Col(
                dbc.Button("Hide ▲", id="controls-toggle", color="link", size="sm",
                           className="controls-toggle-btn p-0"),
                width="auto"),
        ], justify="between", align="center", className="g-0 mb-2 mt-2"),

        dbc.Collapse([
            _control_row(),
            _cache_row(),
        ], id="controls-collapse", is_open=True),

        # Interval fires every 500 ms to poll worker-thread progress
        dcc.Interval(id="progress-interval", interval=500, n_intervals=0),

        # Hidden stores
        dcc.Store(id="top5-store"),

        # Validation errors (owned by the run-btn callback)
        dbc.Alert(id="validation-alert", is_open=False, color="danger", className="mb-2"),

        # Progress section — hidden until a run starts
        html.Div(id="progress-section", style={"display": "none"}, children=[
            html.Div(
                id="progress-step",
                className="mb-1",
                style={"color": "#64748b", "fontSize": "0.9rem", "fontFamily": "monospace"},
            ),
            dbc.Progress(
                id="progress-bar",
                value=0,
                striped=True,
                animated=True,
                color="success",
                style={"height": "22px", "borderRadius": "4px"},
                className="mb-3",
            ),
        ]),

        # Runtime errors / partial-failure warnings (owned by the interval callback)
        dbc.Alert(id="run-alert", is_open=False, color="warning", className="mb-3"),

        # ── Results: hero KPIs + top-5 table ──────────────────────────────────
        html.Div(id="table-section", style={"display": "none"}, children=[
            # Hero metric cards for the selected row (filled by update_kpis)
            html.Div(id="kpi-cards", className="mb-3"),

            dbc.Card(dbc.CardBody([
                html.H5("Best Parameters per Symbol — ranked by Sharpe Ratio",
                        className="card-title mb-3"),
                dash_table.DataTable(
                    id="top5-table",
                    row_selectable="single",
                    selected_rows=[0],
                    style_table={"overflowX": "auto"},
                    style_header={
                        "backgroundColor": "#16a34a",
                        "color": "white",
                        "fontWeight": "bold",
                    },
                    style_data={
                        "backgroundColor": "#ffffff",
                        "color": "#1e293b",
                    },
                    style_data_conditional=[{
                        "if": {"state": "selected"},
                        "backgroundColor": "#dcfce7",
                        "color": "#065f46",
                    }],
                    style_cell={"textAlign": "left", "padding": "6px 12px",
                                "border": "1px solid #eef2f1"},
                    page_action="none",
                ),
                dbc.Row([
                    dbc.Col(
                        dbc.Button(
                            "Save to Scanner", id="save-scanner-btn",
                            color="info", outline=True, size="sm", className="mt-2",
                        ), width="auto",
                    ),
                    dbc.Col(
                        dbc.Alert(
                            id="scanner-alert", is_open=False, duration=4000,
                            className="mb-0 mt-2 py-1 px-2",
                            style={"fontSize": "0.85rem"},
                        ),
                    ),
                ], align="center", className="g-2"),
            ]), className="mb-3"),
        ]),

        # ── Graphs, grouped into sub-tabs so the page stays scannable ─────────
        html.Div(id="graph-section", style={"display": "none"}, children=[
            dbc.Tabs([
                dbc.Tab(label="Overview", tab_id="tab-overview", children=[
                    _graph_card("equity-graph"),
                    _graph_card("benchmark-graph"),
                ]),
                dbc.Tab(label="Trades", tab_id="tab-trades", children=[
                    _graph_card("trades-graph"),
                    dbc.Row([
                        dbc.Col(_graph_card("pnl-dist-graph"), md=6),
                        dbc.Col(_graph_card("monthly-returns-graph"), md=6),
                    ], className="g-3"),
                ]),
                dbc.Tab(label="Robustness", tab_id="tab-robust", children=[
                    _graph_card("montecarlo-graph"),
                    # Walk-forward chart is meaningful only for WF runs; shows a hint otherwise.
                    _graph_card("walkforward-graph"),
                ]),
            ], id="chart-tabs", active_tab="tab-overview", className="mt-2"),

            # Dummy target for the clientside resize-on-tab-switch callback
            html.Div(id="chart-tabs-resize-dummy", style={"display": "none"}),
        ]),
    ]


def _historical_tab():
    """Existing results-browser UI."""
    options = _get_available_results(RESULTS_DIR)
    return [
        dbc.Row(dbc.Col([
            html.Label("Select Saved Run:", className="section-label d-block mb-1"),
            dcc.Dropdown(
                id="run-selector-dd",
                options=options,
                placeholder="Select a run…",
                clearable=False,
            ),
        ]), className="mb-3 mt-2"),

        dbc.Spinner(dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5("Configuration", className="card-title"),
                dcc.Markdown(id="hist-config-display",
                             style={"whiteSpace": "pre", "overflowX": "auto",
                                    "maxHeight": "300px", "backgroundColor": "#ffffff",
                                    "border": "1px solid #e2e8f0", "borderRadius": "8px",
                                    "padding": "10px", "fontSize": "0.8rem"}),
                html.H5("Best Params Summary", className="card-title mt-3"),
                html.Div(id="hist-stats-display"),
            ])), md=5),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H5("Portfolio Plot", className="card-title"),
                dcc.Graph(id="hist-summary-graph", responsive=True,
                          config={"displaylogo": False}),
                html.H5("Trades Plot", className="card-title mt-3"),
                dcc.Graph(id="hist-trades-graph", responsive=True,
                          config={"displaylogo": False}),
            ])), md=7),
        ], id="hist-results-area", style={"display": "none"}, className="g-3")),

        dbc.Row(dbc.Col(dbc.Card(dbc.CardBody([
            html.H5("Trade Records", className="card-title"),
            html.Div(id="hist-trades-table"),
        ])), className="mt-3")),
    ]


app.layout = dbc.Container([
    html.Div([
        html.H2("Healy Labs BT", className="brand-title d-inline align-middle"),
        html.Span("  vectorBT backtesting studio", className="brand-subtitle align-middle"),
    ], className="brand-bar py-3 mb-4"),

    dbc.Tabs([
        dbc.Tab(_results_tab(),    label="Run Backtest",      tab_id="tab-run"),
        dbc.Tab(_historical_tab(), label="Historical Results", tab_id="tab-hist"),
    ], id="main-tabs", active_tab="tab-run"),

], fluid=True, className="app-container py-2")


# ═══════════════════════════════════════════════════════════════════════════
#  CALLBACK 1 — Validate input and launch the worker thread
# ═══════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("validation-alert", "children"),
    Output("validation-alert", "is_open"),
    Input("run-btn", "n_clicks"),
    State("ticker-input", "value"),
    State("start-date",   "value"),
    State("end-date",     "value"),
    State("interval-dd",  "value"),
    State("strategy-dd",  "value"),
    State("wf-toggle",    "value"),
    State("asset-type-dd", "value"),
    prevent_initial_call=True,
)
def start_run(n_clicks, ticker, start, end, interval, strategy, wf_toggle, asset_type):
    """
    Validates the form, then starts a background worker thread and returns
    immediately so the UI stays responsive.  Progress is polled by the interval.
    """
    # ── Validation ──────────────────────────────────────────────────────────
    if not ticker or not ticker.strip():
        return "Please enter at least one ticker symbol.", True

    tickers = list(dict.fromkeys(
        t.strip().upper() for t in ticker.split(",") if t.strip()
    ))
    if not tickers:
        return "Please enter at least one valid ticker symbol.", True

    if not start or not end:
        return "Please set both start and end dates.", True

    if start >= end:
        return "Start date must be before end date.", True

    if strategy not in STRATEGIES:
        return f"Unknown strategy: {strategy}", True

    if strategy in NO_WALKFORWARD and "wf" in (wf_toggle or []):
        return (f"Walk-Forward doesn't apply to '{strategy}' — it trades a single "
                f"contract per signal with no parameter grid to optimize. "
                f"Please uncheck Walk-Forward."), True

    asset_type = asset_type or "stock"
    if asset_type == "options" and "wf" in (wf_toggle or []):
        return ("Walk-Forward is stock-only for now — options execution replays "
                "the best parameter set's signals as option orders, and per-fold "
                "re-optimization isn't wired yet. Please uncheck Walk-Forward."), True

    # ── Load config ─────────────────────────────────────────────────────────
    try:
        config          = config_parser.load_config("config/settings.py")
        backtest_config = config.get("BACKTEST_CONFIG", {})
        strategy_config = config.get(STRATEGIES[strategy]["config_key"], {})
        options_exec_config = config.get("STRATEGY_OPTIONS_SINGLE", {})
    except Exception as e:
        return f"Failed to load config/settings.py: {e}", True

    # ── Start worker ─────────────────────────────────────────────────────────
    with _run_lock:
        _run_state["running"]  = True
        _run_state["pct"]      = 0
        _run_state["step"]     = "Starting…"
        _run_state["result"]   = None
        _run_state["consumed"] = True

    use_walkforward = "wf" in (wf_toggle or [])
    thread = threading.Thread(
        target=_worker,
        args=(tickers, start, end, interval, strategy, backtest_config, strategy_config,
              use_walkforward, asset_type, options_exec_config),
        daemon=True,
    )
    thread.start()
    mode_label = ("walk-forward" if use_walkforward else "standard") \
        + (" · options exec" if asset_type == "options" else "")
    logger.info(f"Worker thread started for {tickers} | {strategy} ({mode_label})")

    return "", False  # clear any previous validation error


# ═══════════════════════════════════════════════════════════════════════════
#  CALLBACK 2 — Poll worker progress every 500 ms and update the UI
# ═══════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("progress-bar",     "value"),
    Output("progress-step",    "children"),
    Output("progress-section", "style"),
    Output("run-alert",        "children"),
    Output("run-alert",        "is_open"),
    Output("top5-store",       "data"),
    Output("top5-table",       "data"),
    Output("top5-table",       "columns"),
    Output("top5-table",       "selected_rows"),
    Output("table-section",    "style"),
    Output("graph-section",    "style"),
    Input("progress-interval", "n_intervals"),
    prevent_initial_call=True,
)
def poll_progress(n_intervals):
    """Reads shared _run_state and updates the progress bar and results."""
    HIDDEN       = {"display": "none"}
    SHOW         = {"display": "block"}
    PROGRESS_VIS = {"display": "block"}
    NU           = no_update

    with _run_lock:
        running  = _run_state["running"]
        pct      = _run_state["pct"]
        step     = _run_state["step"]
        consumed = _run_state["consumed"]
        result   = _run_state["result"]

    # ── Still running — show progress, keep results hidden ──────────────────
    if running:
        label = f"{step}  ({pct}%)"
        return pct, label, PROGRESS_VIS, NU, NU, NU, NU, NU, NU, HIDDEN, HIDDEN

    # ── Worker finished and result not yet shown ────────────────────────────
    if result is not None and not consumed:
        with _run_lock:
            _run_state["consumed"] = True

        all_best_rows = result["all_best_rows"]
        errors        = result["errors"]

        if not all_best_rows:
            err_msg = "No results for any ticker. " + " | ".join(errors)
            return 100, "Complete", HIDDEN, err_msg, True, None, [], [], [0], HIDDEN, HIDDEN

        col_defs, table_rows = _build_table_data(all_best_rows)
        warning = ("Some tickers failed: " + " | ".join(errors)) if errors else ""

        return (
            100, "Complete", HIDDEN,
            warning, bool(warning),
            all_best_rows, table_rows, col_defs, [0],
            SHOW, SHOW,
        )

    # ── Idle — nothing to update ────────────────────────────────────────────
    return NU, NU, NU, NU, NU, NU, NU, NU, NU, NU, NU


# ═══════════════════════════════════════════════════════════════════════════
#  CALLBACK 3 — Update graphs when a table row is clicked
# ═══════════════════════════════════════════════════════════════════════════

def _placeholder_fig(message: str) -> go.Figure:
    """An empty figure with a centered explanatory annotation."""
    fig = go.Figure()
    fig.add_annotation(text=message, xref="paper", yref="paper",
                       x=0.5, y=0.5, showarrow=False,
                       font=dict(size=13, color="gray"))
    fig.update_layout(xaxis={"visible": False}, yaxis={"visible": False})
    return fig


@app.callback(
    Output("equity-graph", "figure"),
    Output("benchmark-graph", "figure"),
    Output("trades-graph", "figure"),
    Output("pnl-dist-graph", "figure"),
    Output("monthly-returns-graph", "figure"),
    Output("montecarlo-graph", "figure"),
    Output("walkforward-graph", "figure"),
    Input("top5-table", "selected_rows"),
    State("top5-store",  "data"),
    prevent_initial_call=True,
)
def update_graphs(selected_rows, top5_data):
    """Generates all per-row figures: equity, benchmark, trades, PnL, monthly,
    Monte Carlo, and (for walk-forward runs) the per-fold OOS breakdown."""
    empty = go.Figure()

    if not selected_rows or top5_data is None:
        return empty, empty, empty, empty, empty, empty, empty

    try:
        row_idx  = selected_rows[0]
        row_data = top5_data[row_idx]
        symbol   = row_data.get("symbol")

        sym_cache  = _last_run["by_symbol"].get(symbol, {})
        portfolio  = sym_cache.get("portfolio")
        price_data = sym_cache.get("price_data")
        wf_folds   = sym_cache.get("wf_folds")

        if portfolio is None or price_data is None:
            return empty, empty, empty, empty, empty, empty, empty

        # Options runs sweep several target DTEs: the portfolio / premium series
        # are dicts keyed by the row's variant (each a one-column portfolio).
        option_series = sym_cache.get("option_series")
        if isinstance(portfolio, dict):
            variant   = row_data.get("variant")
            portfolio = portfolio.get(variant)
            if isinstance(option_series, dict):
                option_series = option_series.get(variant)
            if portfolio is None:
                return empty, empty, empty, empty, empty, empty, empty

        col_int_idx = row_data["portfolio_col_int_idx"]
        col         = portfolio.wrapper.columns[col_int_idx]
        single_pf   = portfolio[col]

        # Options runs carry the stitched premium series: draw trade markers on
        # it (the traded instrument) while the benchmark stays the underlying.
        trades_price  = option_series if option_series is not None else price_data

        fig_equity   = plotting.plot_portfolio_summary(single_pf) or empty
        fig_bench    = plotting.plot_equity_vs_benchmark(single_pf, price_data) or empty
        fig_trades   = plotting.plot_trades(single_pf, trades_price) or empty
        fig_pnl_dist = plotting.plot_trade_pnl_distribution(single_pf) or empty
        fig_monthly  = plotting.plot_monthly_returns(single_pf) or empty
        fig_mc       = (plotting.plot_monte_carlo(single_pf)
                        or _placeholder_fig("Monte Carlo needs at least 5 trades."))

        if wf_folds:
            fig_wf = (plotting.plot_walkforward_folds(wf_folds)
                      or _placeholder_fig("No walk-forward fold data to plot."))
        else:
            fig_wf = _placeholder_fig(
                "Per-fold breakdown appears here when 'Walk-Forward' is enabled.")

        return (fig_equity, fig_bench, fig_trades, fig_pnl_dist,
                fig_monthly, fig_mc, fig_wf)

    except Exception as e:
        logger.error(f"Graph update error: {e}")
        return empty, empty, empty, empty, empty, empty, empty


# ═══════════════════════════════════════════════════════════════════════════
#  CALLBACK 4 — Historical results browser (Tab 2, unchanged)
# ═══════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("hist-results-area",  "style"),
    Output("hist-config-display","children"),
    Output("hist-stats-display", "children"),
    Output("hist-summary-graph", "figure"),
    Output("hist-trades-graph",  "figure"),
    Output("hist-trades-table",  "children"),
    Input("run-selector-dd", "value"),
)
def update_historical(selected_run_id):
    HIDDEN = {"display": "none"}
    SHOW   = {"display": "flex"}

    if not selected_run_id:
        return HIDDEN, "", [], go.Figure(), go.Figure(), []

    run_dir = os.path.join(RESULTS_DIR, selected_run_id)

    config_text  = _load_config_file(run_dir)
    best_stats   = _load_csv(run_dir, BEST_STATS_FILENAME)
    trades_data  = _load_csv(run_dir, TRADES_FILENAME)
    summary_fig  = _load_fig(run_dir, SUMMARY_PLOT_FILE) or go.Figure()
    trades_fig   = _load_fig(run_dir, TRADES_PLOT_FILE)  or go.Figure()

    config_md    = f"```python\n{config_text}\n```"
    stats_table  = _make_stats_table(best_stats)
    trades_table = _make_trades_table(trades_data)

    return SHOW, config_md, stats_table, summary_fig, trades_fig, trades_table


# ═══════════════════════════════════════════════════════════════════════════
#  CALLBACK 5 — Clear data cache
# ═══════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("cache-alert", "children"),
    Output("cache-alert", "is_open"),
    Output("cache-info",  "children"),
    Input("clear-cache-btn", "n_clicks"),
    prevent_initial_call=True,
)
def clear_cache(n_clicks):
    """Deletes all CSV files in the data cache directory."""
    try:
        if not os.path.isdir(CACHE_DIR):
            return "Cache directory not found.", True, "Cache: 0 files (0 B)"

        files = glob.glob(os.path.join(CACHE_DIR, "*.csv"))
        if not files:
            return "Cache is already empty.", True, "Cache: 0 files (0 B)"

        deleted = 0
        for f in files:
            try:
                os.remove(f)
                deleted += 1
            except Exception:
                pass

        count, size = _get_cache_info()
        msg = f"Cleared {deleted} cached file{'s' if deleted != 1 else ''}."
        return msg, True, f"Cache: {count} files ({size})"

    except Exception as e:
        return f"Error clearing cache: {e}", True, "Cache: ? files"


# ═══════════════════════════════════════════════════════════════════════════
#  CALLBACK 6 — Save selected row to scanner
# ═══════════════════════════════════════════════════════════════════════════

# Maps dashboard strategy names → scanner strategy keys + param name mapping.
# Scanner param key ← short name used in param_label (from _shorten_level_name).
_SCANNER_STRATEGY_MAP = {
    "MA Crossover": {
        "scanner_key": "ma",
        "param_map": {"fast": "fast_window", "slow": "slow_window"},
    },
    "RSI Threshold": {
        "scanner_key": "rsi",
        "param_map": {"window": "rsi_window", "entry": "entry_threshold", "exit": "exit_threshold"},
    },
    "MACD Crossover": {
        "scanner_key": "macd",
        "param_map": {"fast": "fast_window", "slow": "slow_window", "signal": "signal_window"},
    },
    "Volume Breakout": {
        "scanner_key": "volume",
        "param_map": {"vol_window": "volume_window", "vol_mult": "volume_multiplier", "exit_ma": "exit_ma_window"},
    },
    "Bollinger Bands": {
        "scanner_key": "bbands",
        "param_map": {"window": "bb_window", "alpha": "bb_alpha"},
    },
    "Stochastic Crossover": {
        "scanner_key": "stoch",
        "param_map": {"k": "k_window", "d": "d_window", "oversold": "oversold", "overbought": "overbought"},
    },
}
# Elliott Wave / Fib and Sentiment are intentionally omitted: the lightweight
# scanner performs a single last-bar indicator check, which does not fit
# Elliott's multi-bar swing detection or Sentiment's external news feed.

def _parse_param_label(param_label: str) -> dict:
    """Parse 'fast=10, slow=50' into {'fast': 10.0, 'slow': 50.0}."""
    result = {}
    for part in param_label.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        key, val = part.split("=", 1)
        try:
            v = float(val.strip())
            result[key.strip()] = int(v) if v == int(v) else v
        except ValueError:
            result[key.strip()] = val.strip()
    return result


@app.callback(
    Output("scanner-alert", "children"),
    Output("scanner-alert", "is_open"),
    Output("scanner-alert", "color"),
    Input("save-scanner-btn", "n_clicks"),
    State("top5-table",  "selected_rows"),
    State("top5-store",  "data"),
    State("strategy-dd", "value"),
    State("interval-dd", "value"),
    prevent_initial_call=True,
)
def save_to_scanner(n_clicks, selected_rows, top5_data, strategy, interval):
    """Saves the selected result row to scanner/saved_scans.json."""
    if not selected_rows or top5_data is None:
        return "No row selected.", True, "warning"

    row = top5_data[selected_rows[0]]
    symbol = row.get("symbol", "")
    param_label = row.get("param_label", "")

    # Check if the strategy is supported by the scanner
    mapping = _SCANNER_STRATEGY_MAP.get(strategy)
    if mapping is None:
        return f"Scanner does not support '{strategy}' yet.", True, "warning"

    # Parse param_label → scanner params
    parsed = _parse_param_label(param_label)
    scanner_params = {}
    for short_name, scanner_key in mapping["param_map"].items():
        if short_name in parsed:
            scanner_params[scanner_key] = parsed[short_name]

    if not scanner_params:
        return f"Could not parse parameters from '{param_label}'.", True, "danger"

    scan_entry = {
        "strategy": mapping["scanner_key"],
        "symbol": symbol,
        "interval": interval,
        "params": scanner_params,
    }

    # Read existing saved scans, append, write back
    saved_path = os.path.join("scanner", "saved_scans.json")
    try:
        existing = []
        if os.path.exists(saved_path):
            with open(saved_path) as f:
                existing = json.load(f)

        # Check for duplicates
        for entry in existing:
            if (entry.get("strategy") == scan_entry["strategy"]
                    and entry.get("symbol") == scan_entry["symbol"]
                    and entry.get("interval") == scan_entry["interval"]
                    and entry.get("params") == scan_entry["params"]):
                return "Already saved to scanner.", True, "info"

        existing.append(scan_entry)
        with open(saved_path, "w") as f:
            json.dump(existing, f, indent=2)

    except Exception as e:
        return f"Error saving: {e}", True, "danger"

    param_str = ", ".join(f"{k}={v}" for k, v in scanner_params.items())
    return (
        f"Saved: {symbol} {mapping['scanner_key'].upper()} ({param_str})",
        True,
        "success",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  CALLBACK 7 — Collapse / expand the controls panel
# ═══════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("controls-collapse", "is_open"),
    Output("controls-toggle",   "children"),
    Input("controls-toggle", "n_clicks"),
    State("controls-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_controls(n_clicks, is_open):
    """Show/hide the ticker/date/strategy inputs so results can take the screen."""
    new_open = not is_open
    return new_open, ("Hide ▲" if new_open else "Show ▼")


# ═══════════════════════════════════════════════════════════════════════════
#  CALLBACK 8 — Hero KPI cards for the selected result row
# ═══════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("kpi-cards", "children"),
    Input("top5-table", "selected_rows"),
    State("top5-store", "data"),
    prevent_initial_call=True,
)
def update_kpis(selected_rows, top5_data):
    """Builds the row of big-number metric cards from the selected table row.

    Reads the raw (unformatted) numbers straight from the top5 store, so this
    works independently of whether the portfolio objects are still cached.
    """
    if not selected_rows or not top5_data:
        return no_update
    try:
        row = top5_data[selected_rows[0]]
    except (IndexError, TypeError, KeyError):
        return no_update

    ret    = row.get("total_return_pct")
    bench  = row.get("benchmark_return_pct")
    sharpe = row.get("sharpe_ratio")
    maxdd  = row.get("max_drawdown_pct")
    winr   = row.get("win_rate_pct")

    # ── Tone (color) logic ────────────────────────────────────────────────────
    ret_tone = "pos" if (ret is not None and ret >= 0) else "neg"
    if sharpe is None:
        sh_tone = "neutral"
    elif sharpe >= 1:
        sh_tone = "pos"
    elif sharpe >= 0:
        sh_tone = "neutral"
    else:
        sh_tone = "neg"
    wr_tone = "pos" if (winr is not None and winr >= 50) else "warn"

    # Excess return vs buy-and-hold, shown as a sub-line under Return
    alpha_sub = None
    if ret is not None and bench is not None:
        alpha_sub = f"{ret - bench:+.1f}% vs B&H"

    caption = html.Div([
        html.Strong(row.get("symbol", "")),
        f"  ·  {row.get('param_label', '')}  ·  ranked by {row.get('ranked_by', 'Sharpe')}",
    ], className="kpi-caption")

    cards = dbc.Row([
        _kpi_card("Return",       _fmt_pct(ret),       ret_tone, alpha_sub),
        _kpi_card("Benchmark",    _fmt_pct(bench),     "neutral"),
        _kpi_card("Sharpe",       _fmt_num(sharpe, 2), sh_tone),
        _kpi_card("Max Drawdown", _fmt_pct(maxdd),     "neg"),
        _kpi_card("Win Rate",     _fmt_pct(winr),      wr_tone),
    ], className="g-2")

    return [caption, cards]


# ── Clientside: resize charts when a chart sub-tab becomes visible ────────────
# Plotly graphs first rendered inside a hidden tab come up collapsed; dispatching
# a window resize once the tab is shown makes the responsive graphs fill their card.
app.clientside_callback(
    """
    function(active_tab) {
        setTimeout(function () { window.dispatchEvent(new Event('resize')); }, 60);
        return "";
    }
    """,
    Output("chart-tabs-resize-dummy", "children"),
    Input("chart-tabs", "active_tab"),
    prevent_initial_call=True,
)


# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
