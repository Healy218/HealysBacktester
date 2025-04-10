# config/settings.py

# --- Data Configuration ---
DATA_CONFIG = {
    "SYMBOL": "SPY",
    "START_DATE": "2020-01-01",
    "END_DATE": "2023-12-31",
    "INTERVAL": "1D",  # e.g., '1m', '5m', '1h', '1D'
    "DATA_PROVIDER": "YahooFinance" # Or 'AlphaVantage', 'CSV', etc. (for future use)
}

# --- Strategy Configuration ---
# Example for MA Crossover
STRATEGY_MA_CROSSOVER = {
    "SHORT_WINDOW": 20,
    "LONG_WINDOW": 50
}

# Example for RSI Threshold (add if you create an RSI script)
STRATEGY_RSI = {
    "RSI_WINDOW": 14,
    "ENTRY_THRESHOLD": 30,
    "EXIT_THRESHOLD": 70
}

# Add more strategy sections as needed...


# --- Backtest Configuration ---
BACKTEST_CONFIG = {
    "INITIAL_CAPITAL": 100000.0,
    "FEES_PERCENT": 0.001,      # 0.1% fee per trade value
    "SLIPPAGE_PERCENT": 0.0005, # 0.05% slippage per trade execution price
    "DEFAULT_SIZE": 0.99,       # Default order size if not overridden
    "DEFAULT_SIZE_TYPE": 'percent', # 'percent' or 'shares'
    "DEFAULT_FREQ": 'D',        # Frequency for portfolio simulation stats ('D' for daily)
    "USE_STOP_LOSS": False,      # Enable/disable SL
    "STOP_LOSS_PERCENT": 0.10,  # e.g., 0.10 for 10% stop loss
    "USE_TAKE_PROFIT": False,    # Enable/disable TP
    "TAKE_PROFIT_PERCENT": 0.20 # e.g., 0.20 for 20% take profit
}

# --- Environment/API Keys (Optional - Better in .env file) ---
# If not using .env, you could put placeholders here, but it's not recommended for secrets
API_KEYS = {
    "ALPHAVANTAGE": "YOUR_AV_KEY_HERE", # Example
    "FINNHUB": "YOUR_FINNHUB_KEY_HERE"   # Example
}

# --- Logging Configuration ---
LOGGING_CONFIG = {
    "LEVEL": "INFO", # DEBUG, INFO, WARNING, ERROR, CRITICAL
    "FILE_PATH": "logs/backtester.log" # Relative to project root
}