# utils/error_handling.py
class BacktesterError(Exception):
    """Base class for exceptions in the backtester application."""
    pass

class DataError(BacktesterError):
    """Exception raised for errors related to data loading or processing."""
    pass

class SignalError(BacktesterError):
    """Exception raised for errors in signal generation."""
    pass

class PortfolioError(BacktesterError):
    """Exception raised for errors in portfolio simulation."""
    pass

class ConfigurationError(BacktesterError):
    """Exception raised for configuration issues."""
    pass

def handle_errors(func):
    """
    Decorator to handle exceptions within backtesting functions.  This decorator
    logs the error and re-raises it.  You can modify it to add more sophisticated
    error handling, like retrying, or sending notifications.

    Args:
        func (callable): The function to decorate.

    Returns:
        callable: The wrapped function.
    """
    import logging
    logger = logging.getLogger(__name__) # Get the logger for this module

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BacktesterError as e:
            logger.error(f"Error in {func.__name__}: {e}")
            raise  # Re-raise the exception after logging
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {e}") # Use logger.exception to include the full traceback
            raise  # Re-raise the exception
        # Note:  It's generally best *not* to catch and swallow general exceptions
        # (like Exception) without re-raising, unless you have a very specific
        # reason to do so, as it can mask problems.

    return wrapper

# Example usage (in other modules):
# from utils.error_handling import handle_errors, DataError
#
# @handle_errors
# def load_data(data_path):
#     if not os.path.exists(data_path):
#         raise DataError(f"Data file not found: {data_path}")
#     # ... data loading logic ...
#
# try:
#     data = load_data("data/missing.csv")
# except DataError as e:
#     print(f"Handled data error: {e}")  #  Good practice to handle it at the appropriate level
