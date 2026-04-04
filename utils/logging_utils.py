# utils/logging_utils.py
import logging
import sys
import os

# Single shared logger name for the entire application.
# Using a fixed name means every module gets the SAME logger object,
# so handlers are only added once no matter how many modules call setup_logging().
_LOGGER_NAME = 'backtester'

def setup_logging(log_level=logging.INFO, log_file=None):
    """
    Sets up and returns the shared application logger.

    Safe to call multiple times — handlers are only added on the first call.
    Subsequent calls return the already-configured logger without adding duplicates.

    Args:
        log_level: Logging level (e.g., logging.INFO, logging.DEBUG).
        log_file: Path to log file. If None, logs to console (stdout).

    Returns:
        logging.Logger: The configured shared logger.
    """
    logger = logging.getLogger(_LOGGER_NAME)

    # If handlers are already attached, the logger is already configured.
    # Return early to prevent duplicate log entries.
    if logger.handlers:
        return logger

    logger.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Always add a console handler so output appears in the terminal too.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Don't propagate to the root logger — avoids double-printing if the root
    # logger has its own handlers (e.g., from basicConfig called elsewhere).
    logger.propagate = False

    return logger
