# utils/file_utils.py

import os
import pandas as pd
import plotly.graph_objects as go
import shutil
import datetime
import traceback
from typing import Optional
from utils.logging_utils import setup_logging

logger = setup_logging(log_file="logs/backtester.log")


def create_results_directory(base_results_dir: str = "results",
                             strategy_name: str = "test",
                             symbol: str = "SYM") -> Optional[str]:
    """
    Creates a unique, timestamped directory for storing backtest results.
    Ensures that the directory name doesn't exceed OS limits.
    """
    run_dir_path = None
    try:
        # Safety: Ensure symbol is a clean string, not a DataFrame/object
        clean_symbol = str(symbol).split('\n')[0][:20].strip() 
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        run_dir_name = f"{strategy_name}_{clean_symbol}_{timestamp}"
        run_dir_path = os.path.join(base_results_dir, run_dir_name)
        
        os.makedirs(run_dir_path, exist_ok=True)
        logger.info(f"Results directory created: {run_dir_path}")
        return run_dir_path
    except Exception as e:
        logger.error(f"Error creating results directory: {e}")
        return None


def save_dataframe_to_csv(df: pd.DataFrame | pd.Series,
                          dir_path: str,
                          filename: str):
    """Saves a pandas DataFrame or Series to a CSV file."""
    if df is None:
        logger.warning(f"DataFrame/Series for '{filename}' is None. Skipping save.")
        return
    if not os.path.isdir(dir_path):
        logger.error(f"Directory '{dir_path}' does not exist. Cannot save '{filename}'.")
        return

    filepath = os.path.join(dir_path, filename)
    try:
        df.to_csv(filepath)
        logger.info(f"Saved: {filepath}")
    except Exception as e:
        logger.error(f"Error saving to {filepath}: {e}")
        traceback.print_exc()


def save_figure_to_json(fig: go.Figure,
                        dir_path: str,
                        filename: str):
    """Saves a Plotly Figure to a JSON file."""
    if fig is None:
        logger.warning(f"Figure for '{filename}' is None. Skipping save.")
        return
    if not os.path.isdir(dir_path):
        logger.error(f"Directory '{dir_path}' does not exist. Cannot save '{filename}'.")
        return

    filepath = os.path.join(dir_path, filename)
    try:
        fig.write_json(filepath)
        logger.info(f"Saved plot: {filepath}")
    except Exception as e:
        logger.error(f"Error saving figure to {filepath}: {e}")
        traceback.print_exc()


def save_config_file(config_source_path: str,
                     dir_path: str,
                     filename: str = "config_used.py"):
    """Copies the config file used to the results directory for reproducibility."""
    if not os.path.isfile(config_source_path):
        logger.error(f"Config source '{config_source_path}' not found. Skipping copy.")
        return
    if not os.path.isdir(dir_path):
        logger.error(f"Directory '{dir_path}' does not exist. Cannot save config.")
        return

    filepath = os.path.join(dir_path, filename)
    try:
        shutil.copy2(config_source_path, filepath)
        logger.info(f"Config snapshot saved: {filepath}")
    except Exception as e:
        logger.error(f"Error copying config to {filepath}: {e}")
        traceback.print_exc()
