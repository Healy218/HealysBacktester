# config/settings.py

# --- Data Configuration ---
DATA_CONFIG = {
    "SYMBOL": "SPY",
    "START_DATE": "2020-01-01",
    "END_DATE": "2025-04-09",
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
    "RSI_WINDOW": [10, 14, 21, 28], 
    "ENTRY_THRESHOLD": [25, 30, 35, 40, 45, 50],
    "EXIT_THRESHOLD": [50, 55, 60, 65, 70, 75],
    "SHORT_ENTRY_THRESHOLD": [50, 55, 60, 65, 70, 75],
    "SHORT_EXIT_THRESHOLD": [25, 30, 35, 40, 45, 50],
}

# Add more strategy sections as needed...


BACKTEST_CONFIG = {
    'INITIAL_CAPITAL': 100000.0,
    'FEES_PERCENT': 0.001,     # 0.1%
    'SLIPPAGE_PERCENT': 0.0005, # 0.05%
    'ENABLE_SHORTING': False,
    # --- Position Sizing ---
    'DEFAULT_SIZE': .9,      # 10,000 per trade
    'DEFAULT_SIZE_TYPE': 'percent', # Options: 'percent', 'amount', 'value' (check vbt docs)

    # --- Stop Loss ---
    'USE_STOP_LOSS': True,     # Set to True to enable stop-loss
    'STOP_LOSS_PERCENT': 0.05, # Example: 5% stop-loss (relative to entry price)

    # --- Take Profit ---
    'USE_TAKE_PROFIT': False,    # Set to True to enable take-profit
    'TAKE_PROFIT_PERCENT': 0.10, # Example: 10% take-profit (relative to entry price)

    # --- Simulation Frequency ---
    'DEFAULT_FREQ': 'D'       # Matches data interval usually ('D', 'H', 'T', etc.)
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