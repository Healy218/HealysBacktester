# utils/config_parser.py

import importlib.util
import os
import sys
from typing import Dict, Any
from utils.logging_utils import setup_logging

logger = setup_logging(log_file="logs/backtester.log")

def load_config(config_path: str = 'config/settings.py') -> Dict[str, Any]:
    """
    Loads configuration settings from a Python file.

    Args:
        config_path (str): The relative path to the configuration Python file
                           (e.g., 'config/settings.py').

    Returns:
        Dict[str, Any]: A dictionary containing the settings. Access nested settings
                       like config['SECTION_NAME']['SETTING_NAME'].

    Raises:
        FileNotFoundError: If the config file does not exist.
        Exception: If there's an error loading or executing the config file.
    """
    # Construct absolute path relative to the project root
    # Assumes this parser is called from a script in the 'scripts' directory
    # or similar depth relative to the project root. Adjust if needed.
    try:
        # Find project root dynamically (assuming utils is one level down)
        utils_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(utils_dir)
    except NameError:
        # Fallback if __file__ is not defined (e.g., interactive session)
        project_root = '.' # Assume current directory is project root

    absolute_config_path = os.path.join(project_root, config_path)

    if not os.path.exists(absolute_config_path):
        raise FileNotFoundError(f"Configuration file not found at: {absolute_config_path}")

    try:
        # Create a module spec
        spec = importlib.util.spec_from_file_location("config.settings", absolute_config_path)
        if spec is None or spec.loader is None:
             raise ImportError(f"Could not create module spec for {absolute_config_path}")

        # Create a new module based on the spec
        settings_module = importlib.util.module_from_spec(spec)

        # Add the config directory to sys.path temporarily if needed for imports within settings.py
        config_dir = os.path.dirname(absolute_config_path)
        if config_dir not in sys.path:
            sys.path.insert(0, config_dir)
            added_to_path = True
        else:
            added_to_path = False

        # Execute the module
        spec.loader.exec_module(settings_module)

        # Remove path if added
        if added_to_path:
             sys.path.pop(0)

        # Extract settings (assuming they are defined as top-level dicts/variables)
        config_dict = {key: value for key, value in settings_module.__dict__.items()
                       if not key.startswith("__") and not isinstance(value, type(sys))} # Exclude built-ins/modules

        logger.info(f"Configuration loaded from: {absolute_config_path}")
        return config_dict

    except Exception as e:
        logger.error(f"Error loading configuration from {absolute_config_path}: {e}")
        raise

# Example usage (if run directly)
if __name__ == "__main__":
    try:
        # Assume this file is in utils/, so look for config/settings.py relative to parent
        default_path = os.path.join('..', 'config', 'settings.py')
        # Adjust path based on actual structure if needed
        # Find the absolute path assuming this script is in HealysBacktester/utils/
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root_dir = os.path.dirname(script_dir)
        correct_config_path_from_utils = os.path.join(project_root_dir,'config','settings.py')

        # Use the relative path format expected by the function
        config = load_config('config/settings.py')
        print("\nLoaded Configuration:")
        import json
        print(json.dumps(config, indent=4, default=str)) # Pretty print

        # Accessing specific settings
        print(f"\nSymbol: {config.get('DATA_CONFIG', {}).get('SYMBOL', 'N/A')}")
        print(f"Short Window: {config.get('STRATEGY_MA_CROSSOVER', {}).get('SHORT_WINDOW', 'N/A')}")
        print(f"Initial Capital: {config.get('BACKTEST_CONFIG', {}).get('INITIAL_CAPITAL', 'N/A')}")

    except Exception as e:
        print(f"Failed to load config in example usage: {e}")