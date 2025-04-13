# main.py

import dash
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc # Using Bootstrap for better styling
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import os
import json
import traceback
from pathlib import Path # Use pathlib for easier path handling

# --- Configuration ---
RESULTS_DIR = "results"
CONFIG_FILENAME = "config_used.py"
BEST_STATS_FILENAME = "best_params_stats.csv"
AGG_STATS_FILENAME = "aggregate_stats.csv"
TRADES_FILENAME = "best_params_trades.csv"
SUMMARY_PLOT_FILENAME = "plot_portfolio_summary.json"
TRADES_PLOT_FILENAME = "plot_trades.json"


# --- Helper Functions ---

def get_available_results(results_base_dir: str) -> list[dict]:
    """Scans the results directory for available backtest run subdirectories."""
    runs = []
    try:
        if os.path.isdir(results_base_dir):
            for item in sorted(os.listdir(results_base_dir), reverse=True): # Sort newest first
                item_path = os.path.join(results_base_dir, item)
                if os.path.isdir(item_path):
                    # Use the directory name as the label and value for the dropdown
                    runs.append({"label": item, "value": item})
    except Exception as e:
        print(f"Error scanning results directory '{results_base_dir}': {e}")
    return runs

def load_config_file(run_dir_path: str) -> str:
    """Loads the content of the saved config file."""
    config_path = os.path.join(run_dir_path, CONFIG_FILENAME)
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return f.read()
        else:
            return "Config file not found."
    except Exception as e:
        print(f"Error loading config file {config_path}: {e}")
        return f"Error loading config: {e}"

def load_stats_csv(run_dir_path: str, filename: str) -> pd.DataFrame | pd.Series | None:
    """Loads a CSV file containing stats into a pandas Series or DataFrame."""
    stats_path = os.path.join(run_dir_path, filename)
    try:
        if os.path.exists(stats_path):
             # Read CSV, assume first column is index (metric names or params)
            df = pd.read_csv(stats_path, index_col=0)
            # If it results in a DataFrame with one column, convert to Series
            if isinstance(df, pd.DataFrame) and df.shape[1] == 1:
                return df.iloc[:, 0]
            return df # Return DataFrame if multiple columns (like aggregate) or Series if read correctly
        else:
             print(f"Stats file not found: {stats_path}")
             return None
    except Exception as e:
        print(f"Error loading stats CSV {stats_path}: {e}")
        return None

def load_plotly_fig_from_json(run_dir_path: str, filename: str) -> go.Figure | None:
     """Loads a Plotly figure from a JSON file."""
     plot_path = os.path.join(run_dir_path, filename)
     try:
         if os.path.exists(plot_path):
              with open(plot_path, 'r') as f:
                   fig_json = json.load(f)
              fig = pio.from_json(json.dumps(fig_json)) # pio needs string dump
              return fig
         else:
              print(f"Plot file not found: {plot_path}")
              return None
     except Exception as e:
        print(f"Error loading Plotly JSON {plot_path}: {e}")
        return None


# --- Initialize Dash App ---
# Use Bootstrap themes for better default styling
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "Healy's Backtester Dashboard" # Browser tab title

# --- App Layout ---
app.layout = dbc.Container([
    dbc.Row(dbc.Col(html.H1("Backtest Results Dashboard"), width=12)),

    dbc.Row([
        dbc.Col([
            html.Label("Select Backtest Run:"),
            dcc.Dropdown(
                id='run-selector-dropdown',
                options=get_available_results(RESULTS_DIR), # Populate dropdown
                placeholder="Select a run...",
                clearable=False
            )
        ], width=12)
    ], className="mb-3"), # Add margin bottom

    dbc.Spinner( # Show spinner while loading
        dbc.Row([
            dbc.Col([
                 html.H3("Configuration Used"),
                 dcc.Markdown(id='config-display', style={'white-space': 'pre', 'overflowX': 'auto', 'maxHeight': '300px', 'border': '1px solid lightgrey', 'padding': '5px'}),
                 html.H3("Best Parameters Performance Summary"),
                 html.Div(id='best-stats-display') # Display best stats table here
            ], width=6), # Half width column for text outputs

            dbc.Col([
                 html.H3("Portfolio Summary Plot"),
                 dcc.Graph(id='summary-plot-display'), # Display summary plot
                 html.H3("Trades Plot"),
                 dcc.Graph(id='trades-plot-display') # Display trades plot
            ], width=6) # Half width column for plots
        ], id='results-output-area', style={'display': 'none'}) # Initially hidden
    ),

    dbc.Row([
         dbc.Col([
             html.H3("Trade Records (Best Parameters)"),
             html.Div(id='trades-table-display') # Display trades table here
         ], width=12)
    ], className="mt-3"), # Add margin top

], fluid=True) # Use fluid container for full width


# --- Callback to Load and Display Results ---
@app.callback(
    [Output('results-output-area', 'style'), # Show/hide the whole area
     Output('config-display', 'children'),
     Output('best-stats-display', 'children'),
     Output('summary-plot-display', 'figure'),
     Output('trades-plot-display', 'figure'),
     Output('trades-table-display', 'children')],
    [Input('run-selector-dropdown', 'value')] # Triggered when dropdown value changes
)
def update_results_display(selected_run_id):
    if not selected_run_id:
        # No run selected, hide output area and return empty outputs
        return {'display': 'none'}, "", [], go.Figure(), go.Figure(), []

    print(f"Loading results for run: {selected_run_id}")
    run_dir_path = os.path.join(RESULTS_DIR, selected_run_id)

    # --- Load Data ---
    config_content = load_config_file(run_dir_path)
    best_stats_data = load_stats_csv(run_dir_path, BEST_STATS_FILENAME)
    trades_data = load_stats_csv(run_dir_path, TRADES_FILENAME)
    summary_fig = load_plotly_fig_from_json(run_dir_path, SUMMARY_PLOT_FILENAME)
    trades_fig = load_plotly_fig_from_json(run_dir_path, TRADES_PLOT_FILENAME)

    # --- Prepare Outputs ---
    # Config (display as preformatted text within Markdown)
    config_markdown = f"```python\n{config_content}\n```"

    # Best Stats Table (convert Series/DataFrame to Dash DataTable)
    best_stats_table = []
    if best_stats_data is not None:
        if isinstance(best_stats_data, pd.Series):
             # Convert Series to DataFrame for DataTable
             stats_df = best_stats_data.reset_index()
             stats_df.columns = ['Metric', 'Value']
        elif isinstance(best_stats_data, pd.DataFrame):
             stats_df = best_stats_data.reset_index() # Assuming index is metric name
             # Handle multi-index columns if necessary from aggregate stats later
        else:
             stats_df = pd.DataFrame({'Error': ['Could not load stats']})

        # Format numbers for display (optional)
        for col in stats_df.columns:
            if pd.api.types.is_numeric_dtype(stats_df[col]):
                 stats_df[col] = stats_df[col].apply(lambda x: f"{x:,.3f}" if pd.notna(x) else x)


        best_stats_table = dash_table.DataTable(
            data=stats_df.to_dict('records'),
            columns=[{'name': i, 'id': i} for i in stats_df.columns],
            style_cell={'textAlign': 'left', 'padding': '5px'},
            style_header={'fontWeight': 'bold'},
            style_table={'overflowX': 'auto'},
        )
    else:
         best_stats_table = html.P("Best stats file not found.")


    # Trades Table
    trades_table_component = []
    if trades_data is not None and not trades_data.empty:
         trades_table_component = dash_table.DataTable(
             data=trades_data.to_dict('records'),
             columns=[{'name': i, 'id': i} for i in trades_data.columns],
             page_size=10, # Add pagination for long trade lists
             style_table={'overflowX': 'auto'},
             style_cell={'minWidth': '80px', 'width': '120px', 'maxWidth': '180px',
                         'overflow': 'hidden', 'textOverflow': 'ellipsis'},
         )
    else:
         trades_table_component = html.P("Trades file not found or no trades executed.")

    # Ensure figures are valid Plotly figures, create empty if None
    summary_fig = summary_fig if summary_fig else go.Figure()
    trades_fig = trades_fig if trades_fig else go.Figure()

    # Return all components to update the layout
    return ({'display': 'flex'}, # Show the results area (use flex for columns)
            config_markdown,
            best_stats_table,
            summary_fig,
            trades_fig,
            trades_table_component)

# --- Run the App ---
if __name__ == '__main__':
    # Set debug=False for production deployment
    app.run(debug=True)