# filename: HealysBacktester/config/settings.py

# config/settings.py

# --- Data Configuration ---
DATA_CONFIG = {
    "SYMBOL": "FUBO",
    "START_DATE": "2025-03-03",
    "END_DATE": "2025-04-30",
    "INTERVAL": "5m",  # e.g., '1m', '5m', '1h', '1D'
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
# Example config/settings.py section
STRATEGY_RSI = {
    'RSI_WINDOW_START': 5,
    'RSI_WINDOW_END': 35,  # Test windows 10 through 30
    'RSI_WINDOW_STEP': 1,

    'ENTRY_THRESHOLD_START': 10.0,
    'ENTRY_THRESHOLD_END': 49.0, # Test thresholds 20.0 through 35.0
    'ENTRY_THRESHOLD_STEP': 0.5,

    'EXIT_THRESHOLD_START': 51.0,
    'EXIT_THRESHOLD_END': 90.0, # Test thresholds 65.0 through 80.0
    'EXIT_THRESHOLD_STEP': 0.5,

    # Only needed if ENABLE_SHORTING is True in BACKTEST_CONFIG
    'SHORT_ENTRY_THRESHOLD_START': 65.0,
    'SHORT_ENTRY_THRESHOLD_END': 80.0,
    'SHORT_ENTRY_THRESHOLD_STEP': 1.0,

    'SHORT_EXIT_THRESHOLD_START': 20.0,
    'SHORT_EXIT_THRESHOLD_END': 35.0,
    'SHORT_EXIT_THRESHOLD_STEP': 1.0,
}

BACKTEST_CONFIG = {
    'INITIAL_CAPITAL': 100000.0,
    'FEES_PERCENT': 0.001,     # 0.1%
    'SLIPPAGE_PERCENT': 0.0005, # 0.05%
    'ENABLE_SHORTING': True, # Enables short trading for MA, RSI strategies
    # --- Position Sizing ---
    'DEFAULT_SIZE': .9,      # Use 90% of equity per trade (leaves 10% as buffer for fees/slippage)
    'DEFAULT_SIZE_TYPE': 'percent', # 'percent' = % of available cash; when ENABLE_SHORTING=True the simulator auto-converts this to 'value' sizing

    # --- Stop Loss ---
    'USE_STOP_LOSS': True,     # Set to True to enable stop-loss
    'STOP_LOSS_PERCENT': 0.05, # Example: 5% stop-loss (relative to entry price)

    # --- Take Profit ---
    'USE_TAKE_PROFIT': False,    # Set to True to enable take-profit
    'TAKE_PROFIT_PERCENT': 0.10, # Example: 10% take-profit (relative to entry price)

    # --- Simulation Frequency ---
    # IMPORTANT: DEFAULT_FREQ must match your data INTERVAL or vectorbt will produce
    # incorrect annualized metrics (Sharpe, CAGR, etc.).
    # Leave as None to auto-detect from DATA_CONFIG['INTERVAL'] via utils.freq_utils.
    # Manual overrides: 'D' = daily, 'h' = hourly, '5min' = 5-minute, '1min' = 1-minute
    'DEFAULT_FREQ': None      # None = auto-detect from INTERVAL (recommended)
}

# Configuration for MACD Strategy - UPDATED FOR RANGES
STRATEGY_MACD = {
    # Fast EMA Window Range
    "FAST_WINDOW_START": 3,
    "FAST_WINDOW_END": 27,  # Tests windows 5 through 20
    "FAST_WINDOW_STEP": 3,

    # Slow EMA Window Range (Must be > Fast Window)
    "SLOW_WINDOW_START": 17,
    "SLOW_WINDOW_END": 42,  # Tests windows 15 through 50
    "SLOW_WINDOW_STEP": 3,

    # Signal Line EMA Window Range
    "SIGNAL_WINDOW_START": 3,
    "SIGNAL_WINDOW_END": 23,  # Tests windows 5 through 20
    "SIGNAL_WINDOW_STEP": 1,

    # Old list-based settings (keep commented or remove)
    # "FAST_WINDOW": [12, 8, 19, 5],
    # "SLOW_WINDOW": [26, 17, 39, 13, 34],
    # "SIGNAL_WINDOW": [9, 5],

    # Shorting control (specific to this strategy)
    "SHORT_ENTRIES_ENABLED": True, # Short entry when MACD crosses below Signal
    "SHORT_EXITS_ENABLED": True   # Short exit when MACD crosses above Signal
}

# Configuration for Volume Breakout Strategy - UPDATED EXIT MA WINDOW
STRATEGY_VOLUME_BREAKOUT = {
    # Define range for volume window
    "VOLUME_WINDOW_START": 30,
    "VOLUME_WINDOW_END": 60,  # Test windows up to 150
    "VOLUME_WINDOW_STEP": 2,
    # Keep volume multiplier as list
    "VOLUME_MULTIPLIER_START": 1.5, # How much higher volume needs to be than average
    "VOLUME_MULTIPLIER_END": 2.00,
    "VOLUME_MULTIPLIER_STEP": 0.1,
    # Define range for exit MA window
    "EXIT_MA_WINDOW_START": 45,
    "EXIT_MA_WINDOW_END": 90,  # Test windows up to 150
    "EXIT_MA_WINDOW_STEP": 1,
    # Other settings
    "CONFIRM_PRICE_INCREASE": False,     # Require close > previous close on breakout day?
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