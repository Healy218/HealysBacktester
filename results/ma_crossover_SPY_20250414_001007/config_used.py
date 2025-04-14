# filename: HealysBacktester/config/settings.py

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

# MA Crossover - Updated for Optimization
STRATEGY_MA_CROSSOVER = {
    # Define the range for window parameters (short and long will be combinations from this range)
    # np.arange(start, end) generates numbers up to end-1.
    # Using 2 to 143 gives windows 2, 3, ..., 142.
    # Combinations (r=2) where short < long: 141 * 140 / 2 = 9870 combinations
    "MA_WINDOW_START": 2,
    "MA_WINDOW_END": 143, # Test windows up to 142
    "MA_WINDOW_STEP": 1, # Optional, defaults to 1
    # "SHORT_WINDOW": 20, # Keep old single values commented or remove
    # "LONG_WINDOW": 50
}

# Example for RSI Threshold (add if you create an RSI script)
STRATEGY_RSI = {
    "RSI_WINDOW": [10, 14, 21, 28],
    "ENTRY_THRESHOLD": [25, 30, 35, 40, 45, 50],
    "EXIT_THRESHOLD": [50, 55, 60, 65, 70, 75],
    "SHORT_ENTRY_THRESHOLD": [50, 55, 60, 65, 70, 75],
    "SHORT_EXIT_THRESHOLD": [25, 30, 35, 40, 45, 50],
}


BACKTEST_CONFIG = {
    'INITIAL_CAPITAL': 100000.0,
    'FEES_PERCENT': 0.001,     # 0.1%
    'SLIPPAGE_PERCENT': 0.0005, # 0.05%
    'ENABLE_SHORTING': False, # MA Crossover script currently doesn't support shorting
    # --- Position Sizing ---
    'DEFAULT_SIZE': .9,      # Use 90% of equity per trade
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

# Configuration for MACD Strategy
STRATEGY_MACD = {
    "FAST_WINDOW": [12, 8, 19, 5],       # Standard default: 12 periods
    "SLOW_WINDOW": [26, 17, 39, 13, 34],       # Standard default: 26 periods
    "SIGNAL_WINDOW": [9, 5],      # Standard default: 9 periods
    # Add more values to the lists above to test multiple parameters, e.g., [12, 15]
    "SHORT_ENTRIES_ENABLED": False, # Set to True to enable shorting based on MACD<Signal cross
    "SHORT_EXITS_ENABLED": False  # Set to True if enabling shorts
}

# Configuration for Volume Breakout Strategy
STRATEGY_VOLUME_BREAKOUT = {
    "VOLUME_WINDOW": [5, 10, 15, 20, 25, 30, 50, 60, 120, 150, 180],          # Lookback period for average volume
    "VOLUME_MULTIPLIER": [1.25, 1.33, 1.5, 1.75, 2.0, 2.5], # How much higher volume needs to be than average
    "CONFIRM_PRICE_INCREASE": False,     # Require close > previous close on breakout day?
    # ****** ADDED Exit Parameter ******
    "EXIT_MA_WINDOW": [10, 20, 30, 50, 60, 120, 150, 180]             # Exit when close crosses below this SMA window
                                        # Add more values like [10, 15] to test multiple exits
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