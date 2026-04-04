# main.py — Healy's Backtester Interactive Dashboard
#
# Tab 1: Run a backtest live — pick ticker, dates, interval, strategy → top-5 results + graphs.
# Tab 2: Browse previously saved backtest result directories.
#
# Run from the project root:  python main.py
# Then open:  http://127.0.0.1:8050

import os
import json
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
from backtests import run_ma, run_rsi, run_macd, run_volume

logger = setup_logging(log_file="logs/backtester.log")

# ── Constants ───────────────────────────────────────────────────────────────
RESULTS_DIR          = "results"
CONFIG_FILENAME      = "config_used.py"
BEST_STATS_FILENAME  = "best_params_stats.csv"
TRADES_FILENAME      = "best_params_trades.csv"
SUMMARY_PLOT_FILE    = "plot_portfolio_summary.json"
TRADES_PLOT_FILE     = "plot_trades.json"

STRATEGIES = {
    "MA Crossover":    {"runner": run_ma,     "config_key": "STRATEGY_MA_CROSSOVER"},
    "RSI Threshold":   {"runner": run_rsi,    "config_key": "STRATEGY_RSI"},
    "MACD Crossover":  {"runner": run_macd,   "config_key": "STRATEGY_MACD"},
    "Volume Breakout": {"runner": run_volume, "config_key": "STRATEGY_VOLUME_BREAKOUT"},
}

INTERVALS = [
    {"label": "1 Minute  (≤7 days, yfinance / Alpaca)",  "value": "1m"},
    {"label": "5 Minutes (≤60 days, yfinance / Alpaca)", "value": "5m"},
    {"label": "15 Minutes",                               "value": "15m"},
    {"label": "1 Hour",                                   "value": "1h"},
    {"label": "1 Day",                                    "value": "1D"},
]

# ── In-memory state (not stored in dcc.Store — not JSON-serialisable) ───────
_last_run: dict = {"portfolio": None, "price_data": None}

# ── App ─────────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    title="Healy's Backtester",
)

# ── Helper functions (defined here so layout functions can call them) ────────

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


# ═══════════════════════════════════════════════════════════════════════════
#  LAYOUT
# ═══════════════════════════════════════════════════════════════════════════

def _control_row():
    """The top input bar for Tab 1."""
    today      = date.today()
    one_yr_ago = today - timedelta(days=365)
    return dbc.Card(dbc.CardBody(dbc.Row([

        dbc.Col([
            dbc.Label("Ticker"),
            dbc.Input(id="ticker-input", placeholder="e.g. SPY", type="text",
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


def _results_tab():
    return [
        _control_row(),

        # Hidden stores — JSON-serialisable payload only
        dcc.Store(id="top5-store"),

        dcc.Loading(
            id="loading",
            type="circle",
            color="#00bc8c",
            children=[

                # Error banner
                dbc.Alert(id="error-alert", is_open=False, color="danger",
                          className="mb-3"),

                # Top-5 table (hidden until a run completes)
                html.Div(id="table-section", style={"display": "none"}, children=[
                    html.H5("Top 5 Parameter Combinations — ranked by Sharpe Ratio",
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

                # Graphs (hidden until a row is selected)
                html.Div(id="graph-section", style={"display": "none"}, children=[
                    dbc.Row([
                        dbc.Col(dcc.Graph(id="equity-graph"), md=12),
                    ], className="mt-3"),
                    dbc.Row([
                        dbc.Col(dcc.Graph(id="trades-graph"), md=12),
                    ], className="mt-3"),
                ]),

            ],
        ),
    ]


def _historical_tab():
    """Existing results-browser UI, now in its own tab."""
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
    dbc.Row(dbc.Col(html.H2("⚡ Healy's Backtester", className="my-3"))),

    dbc.Tabs([
        dbc.Tab(_results_tab(),    label="Run Backtest",      tab_id="tab-run"),
        dbc.Tab(_historical_tab(), label="Historical Results", tab_id="tab-hist"),
    ], id="main-tabs", active_tab="tab-run"),

], fluid=True)


# ═══════════════════════════════════════════════════════════════════════════
#  CALLBACK 1 — Run the backtest when the button is clicked
# ═══════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("top5-store",    "data"),
    Output("top5-table",    "data"),
    Output("top5-table",    "columns"),
    Output("table-section", "style"),
    Output("graph-section", "style"),
    Output("error-alert",   "children"),
    Output("error-alert",   "is_open"),
    Output("top5-table",    "selected_rows"),
    Input("run-btn", "n_clicks"),
    State("ticker-input", "value"),
    State("start-date",   "value"),
    State("end-date",     "value"),
    State("interval-dd",  "value"),
    State("strategy-dd",  "value"),
    prevent_initial_call=True,
)
def run_backtest_callback(n_clicks, ticker, start, end, interval, strategy):
    """Runs the selected strategy and populates the top-5 table."""
    HIDDEN = {"display": "none"}
    SHOW   = {"display": "block"}

    # ── Input validation ────────────────────────────────────────────────────
    if not ticker or not ticker.strip():
        return no_update, [], [], HIDDEN, HIDDEN, "Please enter a ticker symbol.", True, [0]

    ticker = ticker.strip().upper()

    if not start or not end:
        return no_update, [], [], HIDDEN, HIDDEN, "Please set both start and end dates.", True, [0]

    if start >= end:
        return no_update, [], [], HIDDEN, HIDDEN, "Start date must be before end date.", True, [0]

    if strategy not in STRATEGIES:
        return no_update, [], [], HIDDEN, HIDDEN, f"Unknown strategy: {strategy}", True, [0]

    # ── Load config ─────────────────────────────────────────────────────────
    try:
        config          = config_parser.load_config("config/settings.py")
        backtest_config = config.get("BACKTEST_CONFIG", {})
        strategy_config = config.get(STRATEGIES[strategy]["config_key"], {})
    except Exception as e:
        msg = f"Failed to load config/settings.py: {e}"
        return no_update, [], [], HIDDEN, HIDDEN, msg, True, [0]

    # ── Run the backtest ────────────────────────────────────────────────────
    runner = STRATEGIES[strategy]["runner"]
    logger.info(f"Dashboard run: {strategy} | {ticker} | {interval} | {start}->{end}")

    result = runner.run(ticker, start, end, interval, backtest_config, strategy_config)

    # Stash non-serialisable objects in module-level cache
    _last_run["portfolio"]   = result.pop("portfolio",   None)
    _last_run["price_data"]  = result.pop("price_data",  None)

    if result.get("error"):
        return (
            None, [], [], HIDDEN, HIDDEN,
            f"Error: {result['error']}", True, [0],
        )

    top5 = result.get("top5", [])
    if not top5:
        return (
            None, [], [], HIDDEN, HIDDEN,
            "No results returned — try a different ticker, date range, or strategy.", True, [0],
        )

    # ── Format table ────────────────────────────────────────────────────────
    col_defs = [
        {"name": "Rank",           "id": "rank"},
        {"name": "Parameters",     "id": "param_label"},
        {"name": "Return %",       "id": "total_return_pct"},
        {"name": "Sharpe",         "id": "sharpe_ratio"},
        {"name": "Max DD %",       "id": "max_drawdown_pct"},
        {"name": "Win Rate %",     "id": "win_rate_pct"},
        {"name": "# Trades",       "id": "total_trades"},
    ]

    table_rows = []
    for row in top5:
        table_rows.append({
            "rank":             row["rank"],
            "param_label":      row["param_label"],
            "total_return_pct": _fmt_pct(row.get("total_return_pct")),
            "sharpe_ratio":     _fmt_num(row.get("sharpe_ratio"), 3),
            "max_drawdown_pct": _fmt_pct(row.get("max_drawdown_pct")),
            "win_rate_pct":     _fmt_pct(row.get("win_rate_pct")),
            "total_trades":     row.get("total_trades", 0),
        })

    return top5, table_rows, col_defs, SHOW, SHOW, "", False, [0]


# ═══════════════════════════════════════════════════════════════════════════
#  CALLBACK 2 — Update graphs when a table row is clicked
# ═══════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("equity-graph", "figure"),
    Output("trades-graph", "figure"),
    Input("top5-table", "selected_rows"),
    State("top5-store",  "data"),
    prevent_initial_call=True,
)
def update_graphs(selected_rows, top5_data):
    """Generates equity + trades graphs for the selected top-5 row."""
    empty = go.Figure()

    if not selected_rows or top5_data is None:
        return empty, empty

    portfolio  = _last_run.get("portfolio")
    price_data = _last_run.get("price_data")

    if portfolio is None or price_data is None:
        return empty, empty

    try:
        row_idx     = selected_rows[0]
        row_data    = top5_data[row_idx]
        col_int_idx = row_data["portfolio_col_int_idx"]

        # Slice to the single chosen combination using integer position
        col       = portfolio.wrapper.columns[col_int_idx]
        single_pf = portfolio[col]

        fig_equity = plotting.plot_portfolio_summary(single_pf) or empty
        fig_trades = plotting.plot_trades(single_pf, price_data) or empty

        return fig_equity, fig_trades

    except Exception as e:
        logger.error(f"Graph update error: {e}")
        return empty, empty


# ═══════════════════════════════════════════════════════════════════════════
#  CALLBACK 3 — Historical results browser (Tab 2, unchanged logic)
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

    config_text   = _load_config_file(run_dir)
    best_stats    = _load_csv(run_dir, BEST_STATS_FILENAME)
    trades_data   = _load_csv(run_dir, TRADES_FILENAME)
    summary_fig   = _load_fig(run_dir, SUMMARY_PLOT_FILE)  or go.Figure()
    trades_fig    = _load_fig(run_dir, TRADES_PLOT_FILE)   or go.Figure()

    config_md = f"```python\n{config_text}\n```"

    stats_table = _make_stats_table(best_stats)
    trades_table = _make_trades_table(trades_data)

    return SHOW, config_md, stats_table, summary_fig, trades_fig, trades_table

# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
