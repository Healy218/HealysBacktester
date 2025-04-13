# utils/file_utils.py

import os
import pandas as pd
import plotly.graph_objects as go
import shutil
import datetime
import traceback
from typing import Optional # Import Optional

def create_results_directory(base_results_dir: str = "results",
                             strategy_name: str = "test",
                             symbol: str = "SYM") -> Optional[str]:
    """
    Creates a unique, timestamped directory for storing backtest results.

    Args:
        base_results_dir: The root directory for all results (e.g., 'results').
        strategy_name: Name of the strategy run (e.g., 'rsi_crossover').
        symbol: Symbol tested (e.g., 'SPY').

    Returns:
        The path to the newly created directory, or None if creation fails.
    """
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir_name = f"{strategy_name}_{symbol}_{timestamp}"
        run_dir_path = os.path.join(base_results_dir, run_dir_name)
        os.makedirs(run_dir_path, exist_ok=True)
        print(f"Results directory created: {run_dir_path}")
        return run_dir_path
    except Exception as e:
        print(f"Error creating results directory '{run_dir_path}': {e}")
        traceback.print_exc()
        return None

def save_dataframe_to_csv(df: pd.DataFrame | pd.Series,
                          dir_path: str,
                          filename: str):
    """
    Saves a pandas DataFrame or Series to a CSV file in the specified directory.

    Args:
        df: The pandas DataFrame or Series to save.
        dir_path: The directory path where the file should be saved.
        filename: The name for the CSV file (e.g., 'trades.csv').
    """
    if df is None:
        print(f"Warning: DataFrame/Series provided for '{filename}' is None. Skipping save.")
        return
    if not os.path.isdir(dir_path):
        print(f"Error: Directory '{dir_path}' does not exist. Cannot save '{filename}'.")
        return

    filepath = os.path.join(dir_path, filename)
    try:
        df.to_csv(filepath)
        print(f"Saved DataFrame/Series to: {filepath}")
    except Exception as e:
        print(f"Error saving DataFrame/Series to {filepath}: {e}")
        traceback.print_exc()

def save_figure_to_json(fig: go.Figure,
                        dir_path: str,
                        filename: str):
    """
    Saves a Plotly Figure object to a JSON file in the specified directory.

    Args:
        fig: The Plotly Figure object.
        dir_path: The directory path where the file should be saved.
        filename: The name for the JSON file (e.g., 'summary_plot.json').
    """
    if fig is None:
        print(f"Warning: Figure provided for '{filename}' is None. Skipping save.")
        return
    if not os.path.isdir(dir_path):
        print(f"Error: Directory '{dir_path}' does not exist. Cannot save '{filename}'.")
        return

    filepath = os.path.join(dir_path, filename)
    try:
        fig.write_json(filepath)
        print(f"Saved Plotly figure to: {filepath}")
    except Exception as e:
        print(f"Error saving Plotly figure to {filepath}: {e}")
        traceback.print_exc()

def save_config_file(config_source_path: str,
                     dir_path: str,
                     filename: str = "config_used.py"):
    """
    Copies the specified configuration file to the results directory.

    Args:
        config_source_path: The path to the original config file used (e.g., 'config/settings.py').
        dir_path: The results directory path where the config should be copied.
        filename: The name for the copied config file within the results directory.
    """
    if not os.path.isfile(config_source_path):
         print(f"Error: Config source file '{config_source_path}' not found. Skipping copy.")
         return
    if not os.path.isdir(dir_path):
        print(f"Error: Directory '{dir_path}' does not exist. Cannot save config copy.")
        return

    filepath = os.path.join(dir_path, filename)
    try:
        shutil.copy2(config_source_path, filepath) # copy2 preserves metadata
        print(f"Saved config file copy to: {filepath}")
    except Exception as e:
        print(f"Error copying config file to {filepath}: {e}")
        traceback.print_exc()