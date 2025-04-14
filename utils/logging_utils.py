# utils/logging_utils.py
import logging
import sys
import os

def setup_logging(log_level=logging.INFO, log_file=None):
    """
    Sets up logging for the application.

    Args:
        log_level (int, optional): The logging level. Defaults to logging.INFO.
        log_file (str, optional): The name of the log file. If None, logs to console.
    """
    logger = logging.getLogger(__name__)  # Use __name__ for module-level logger
    logger.setLevel(log_level)

    # Create a formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Create handlers (either file or console)
    if log_file:
        # Ensure the directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    else:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Optional: Prevent duplicate log messages if the logger was already configured
    logger.propagate = False

    return logger

# Example usage (in other modules):
# from utils.logging_utils import setup_logging
# logger = setup_logging(log_level=logging.INFO, log_file="logs/backtester.log")
# logger.info("Starting the backtest...")
# ...
# logger.error("An error occurred: %s", error_message)

