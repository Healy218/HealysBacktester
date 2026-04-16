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
from backtests import run_ma, run_rsi, run_macd, run_volume, run_bbands, run_stoch, run_elliott, run_sentiment

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
}

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


def _worker(tickers, start, end, interval, strategy, backtest_config, strategy_config):
    """
    Background thread: runs the full backtest for every ticker, writing progress
    updates to _run_state so the Dash interval callback can display them.
    """
    try:
        _set_progress(5, "Configuration loaded")
        runner = STRATEGIES[strategy]["runner"]
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
                "portfolio":  result.pop("portfolio",  None),
                "price_data": result.pop("price_data", None),
            }

            if result.get("error"):
                errors.append(f"{sym}: {result['error']}")
                _set_progress(base + chunk, f"[{sym}] Error")
                continue

            top5 = result.get("top5", [])
            if not top5:
                errors.append(f"{sym}: no results returned")
                _set_progress(base + chunk, f"[{sym}] No results")
                continue

            for row in top5:
                r = row.copy()
                r["symbol"] = sym
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
    external_stylesheets=[dbc.themes.DARKLY],
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
                    "backgroundColor": "#303030", "color": "white"},
        style_header={"backgroundColor": "#375a7f", "color": "white", "fontWeight": "bold"},
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
                    "backgroundColor": "#303030", "color": "white"},
        style_header={"backgroundColor": "#375a7f", "color": "white", "fontWeight": "bold"},
    )


def _build_table_data(all_best_rows):
    """Convert all_best_rows into the col_defs + table_rows the DataTable needs."""
    col_defs = [
        {"name": "Symbol",       "id": "symbol"},
        {"name": "Ranked By",    "id": "ranked_by"},
        {"name": "Parameters",   "id": "param_label"},
        {"name": "Return %",     "id": "total_return_pct"},
        {"name": "Sharpe",       "id": "sharpe_ratio"},
        {"name": "Max DD %",     "id": "max_drawdown_pct"},
        {"name": "Win Rate %",   "id": "win_rate_pct"},
        {"name": "Best Trade %", "id": "best_trade_pct"},
        {"name": "# Trades",     "id": "total_trades"},
    ]
    table_rows = []
    for row in all_best_rows:
        table_rows.append({
            "symbol":           row["symbol"],
            "ranked_by":        row.get("ranked_by", ""),
            "param_label":      row["param_label"],
            "total_return_pct": _fmt_pct(row.get("total_return_pct")),
            "sharpe_ratio":     _fmt_num(row.get("sharpe_ratio"), 3),
            "max_drawdown_pct": _fmt_pct(row.get("max_drawdown_pct")),
            "win_rate_pct":     _fmt_pct(row.get("win_rate_pct")),
            "best_trade_pct":   _fmt_pct(row.get("best_trade_pct")),
            "total_trades":     row.get("total_trades", 0),
        })
    return col_defs, table_rows


# ═══════════════════════════════════════════════════════════════════════════
#  LAYOUT
# ═══════════════════════════════════════════════════════════════════════════

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
            dbc.Label("\u00a0"),   # non-breaking space to align button
            dbc.Button(
                "▶  Run Backtest", id="run-btn", color="success",
                className="w-100",
            ),
        ], xs=12, sm=6, md=2),

    ], align="end", className="g-3")), className="mb-3")


def _cache_row():
    """Cache management bar below the control row."""
    count, size = _get_cache_info()
    return dbc.Card(dbc.CardBody(dbc.Row([
        dbc.Col([
            html.Span(
                f"Cache: {count} files ({size})",
                id="cache-info",
                style={"color": "#aaaaaa", "fontSize": "0.85rem", "fontFamily": "monospace"},
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
        _control_row(),
        _cache_row(),

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
                style={"color": "#aaaaaa", "fontSize": "0.9rem", "fontFamily": "monospace"},
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

        # Top-5 results table
        html.Div(id="table-section", style={"display": "none"}, children=[
            html.H5("Best Parameters per Symbol — ranked by Sharpe Ratio",
                    className="mt-3"),
            dash_table.DataTable(
                id="top5-table",
                row_selectable="single",
                selected_rows=[0],
                style_table={"overflowX": "auto"},
                style_header={
                    "backgroundColor": "#375a7f",
                    "color": "white",
                    "fontWeight": "bold",
                },
                style_data={
                    "backgroundColor": "#303030",
                    "color": "white",
                },
                style_data_conditional=[{
                    "if": {"state": "selected"},
                    "backgroundColor": "#00bc8c",
                    "color": "black",
                }],
                style_cell={"textAlign": "left", "padding": "6px 12px"},
                page_action="none",
            ),
        ]),

        # Graphs (no dcc.Loading wrapper — progress bar replaces the spinner)
        html.Div(id="graph-section", style={"display": "none"}, children=[
            dbc.Row([
                dbc.Col(dcc.Graph(id="equity-graph"), md=12),
            ], className="mt-3"),
            dbc.Row([
                dbc.Col(dcc.Graph(id="trades-graph"), md=12),
            ], className="mt-3"),
            dbc.Row([
                dbc.Col(dcc.Graph(id="pnl-dist-graph"), md=6),
                dbc.Col(dcc.Graph(id="monthly-returns-graph"), md=6),
            ], className="mt-3"),
        ]),
    ]


def _historical_tab():
    """Existing results-browser UI."""
    options = _get_available_results(RESULTS_DIR)
    return [
        dbc.Row(dbc.Col([
            html.Label("Select Saved Run:"),
            dcc.Dropdown(
                id="run-selector-dd",
                options=options,
                placeholder="Select a run…",
                clearable=False,
            ),
        ]), className="mb-3"),

        dbc.Spinner(dbc.Row([
            dbc.Col([
                html.H5("Configuration"),
                dcc.Markdown(id="hist-config-display",
                             style={"whiteSpace": "pre", "overflowX": "auto",
                                    "maxHeight": "300px",
                                    "border": "1px solid #444", "padding": "6px"}),
                html.H5("Best Params Summary", className="mt-3"),
                html.Div(id="hist-stats-display"),
            ], md=5),
            dbc.Col([
                html.H5("Portfolio Plot"),
                dcc.Graph(id="hist-summary-graph"),
                html.H5("Trades Plot", className="mt-3"),
                dcc.Graph(id="hist-trades-graph"),
            ], md=7),
        ], id="hist-results-area", style={"display": "none"})),

        dbc.Row(dbc.Col([
            html.H5("Trade Records", className="mt-3"),
            html.Div(id="hist-trades-table"),
        ])),
    ]


app.layout = dbc.Container([
    dbc.Row(dbc.Col(html.H2("∞Healy Labs BT∞", className="my-3"))),

    dbc.Tabs([
        dbc.Tab(_results_tab(),    label="Run Backtest",      tab_id="tab-run"),
        dbc.Tab(_historical_tab(), label="Historical Results", tab_id="tab-hist"),
    ], id="main-tabs", active_tab="tab-run"),

], fluid=True)


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
    prevent_initial_call=True,
)
def start_run(n_clicks, ticker, start, end, interval, strategy):
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

    # ── Load config ─────────────────────────────────────────────────────────
    try:
        config          = config_parser.load_config("config/settings.py")
        backtest_config = config.get("BACKTEST_CONFIG", {})
        strategy_config = config.get(STRATEGIES[strategy]["config_key"], {})
    except Exception as e:
        return f"Failed to load config/settings.py: {e}", True

    # ── Start worker ─────────────────────────────────────────────────────────
    with _run_lock:
        _run_state["running"]  = True
        _run_state["pct"]      = 0
        _run_state["step"]     = "Starting…"
        _run_state["result"]   = None
        _run_state["consumed"] = True

    thread = threading.Thread(
        target=_worker,
        args=(tickers, start, end, interval, strategy, backtest_config, strategy_config),
        daemon=True,
    )
    thread.start()
    logger.info(f"Worker thread started for {tickers} | {strategy}")

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

@app.callback(
    Output("equity-graph", "figure"),
    Output("trades-graph", "figure"),
    Output("pnl-dist-graph", "figure"),
    Output("monthly-returns-graph", "figure"),
    Input("top5-table", "selected_rows"),
    State("top5-store",  "data"),
    prevent_initial_call=True,
)
def update_graphs(selected_rows, top5_data):
    """Generates equity + trades + PnL distribution + monthly returns for the selected row."""
    empty = go.Figure()

    if not selected_rows or top5_data is None:
        return empty, empty, empty, empty

    try:
        row_idx  = selected_rows[0]
        row_data = top5_data[row_idx]
        symbol   = row_data.get("symbol")

        sym_cache  = _last_run["by_symbol"].get(symbol, {})
        portfolio  = sym_cache.get("portfolio")
        price_data = sym_cache.get("price_data")

        if portfolio is None or price_data is None:
            return empty, empty, empty, empty

        col_int_idx = row_data["portfolio_col_int_idx"]
        col         = portfolio.wrapper.columns[col_int_idx]
        single_pf   = portfolio[col]

        fig_equity   = plotting.plot_portfolio_summary(single_pf) or empty
        fig_trades   = plotting.plot_trades(single_pf, price_data) or empty
        fig_pnl_dist = plotting.plot_trade_pnl_distribution(single_pf) or empty
        fig_monthly  = plotting.plot_monthly_returns(single_pf) or empty

        return fig_equity, fig_trades, fig_pnl_dist, fig_monthly

    except Exception as e:
        logger.error(f"Graph update error: {e}")
        return empty, empty, empty, empty


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
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
