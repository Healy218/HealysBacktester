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

# MA Crossover - Wide parameter sweep
# np.arange(2, 252, 1) → 250 windows → C(250,2) = 31,125 fast/slow combinations
STRATEGY_MA_CROSSOVER = {
    "MA_WINDOW_START": 2,
    "MA_WINDOW_END":   252,  # windows 2..251
    "MA_WINDOW_STEP":  1,
}

# RSI Threshold - Wide parameter sweep
# Windows: 2..50 (49 values)
# Entry thresholds: 5.0..49.5 step 0.5 (90 values)
# Exit  thresholds: 50.0..94.5 step 0.5 (90 values)
# Entry and exit counts MUST match — vectorbt aligns them positionally.
# Total portfolio columns: 49 windows × 90 thresholds = 4,410
STRATEGY_RSI = {
    'RSI_WINDOW_START': 2,
    'RSI_WINDOW_END':   51,   # windows 2..50
    'RSI_WINDOW_STEP':  1,

    'ENTRY_THRESHOLD_START': 5.0,
    'ENTRY_THRESHOLD_END':   50.0,  # 5.0..49.5, step 0.5 → 90 values
    'ENTRY_THRESHOLD_STEP':  0.5,

    'EXIT_THRESHOLD_START': 50.0,
    'EXIT_THRESHOLD_END':   95.0,   # 50.0..94.5, step 0.5 → 90 values
    'EXIT_THRESHOLD_STEP':  0.5,
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

# MACD Strategy - Wide parameter sweep
# Fast: 2..29 (28 values), Slow: 10..59 (50 values), Signal: 2..19 (18 values)
# Valid fast < slow pairs: ~1,190 → × 18 signal = ~21,420 combos
STRATEGY_MACD = {
    "FAST_WINDOW_START":   2,
    "FAST_WINDOW_END":     30,  # fast windows 2..29
    "FAST_WINDOW_STEP":    1,

    "SLOW_WINDOW_START":   10,
    "SLOW_WINDOW_END":     60,  # slow windows 10..59
    "SLOW_WINDOW_STEP":    1,

    "SIGNAL_WINDOW_START": 2,
    "SIGNAL_WINDOW_END":   20,  # signal windows 2..19
    "SIGNAL_WINDOW_STEP":  1,

    "SHORT_ENTRIES_ENABLED": True,
    "SHORT_EXITS_ENABLED":   True,
}

# Volume Breakout Strategy - Wide parameter sweep
# Vol window: 10..99 step 2 (45 values) × Multiplier: 1.1..2.9 step 0.1 (19 values)
# × Exit MA: 10..99 step 2 (45 values) = ~38,475 combos
STRATEGY_VOLUME_BREAKOUT = {
    "VOLUME_WINDOW_START":    10,
    "VOLUME_WINDOW_END":      100,  # volume lookback 10..99, step 2
    "VOLUME_WINDOW_STEP":     2,

    "VOLUME_MULTIPLIER_START": 1.1,
    "VOLUME_MULTIPLIER_END":   3.0,  # 1.1..2.9, step 0.1 → 19 values
    "VOLUME_MULTIPLIER_STEP":  0.1,

    "EXIT_MA_WINDOW_START":   10,
    "EXIT_MA_WINDOW_END":     100,  # exit MA 10..99, step 2
    "EXIT_MA_WINDOW_STEP":    2,

    "CONFIRM_PRICE_INCREASE": False,
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