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
    # Window ranges to sweep.  The right range depends on the data interval:
    #   1m  data → use 20–200  (smaller windows fire hundreds of signals/day → fee drain)
    #   5m  data → use 10–250
    #   1h  data → use  5–100
    #   1D  data → use  2–451  (~100k combos: n*(n-1)/2)
    # Combinations (r=2) where fast < slow: n*(n-1)/2
    # 449 windows → 449*448/2 = 100,576 combos
    "MA_WINDOW_START": 2,
    "MA_WINDOW_END": 451,
    "MA_WINDOW_STEP": 1,
}

# RSI Threshold
# True cross-product: windows × entry_thresholds × exit_thresholds
# 20 windows × 71 entry × 71 exit = 100,820 combos
STRATEGY_RSI = {
    'RSI_WINDOW_START': 5,
    'RSI_WINDOW_END': 25,   # 20 windows (5–24)
    'RSI_WINDOW_STEP': 1,

    'ENTRY_THRESHOLD_START': 10.0,
    'ENTRY_THRESHOLD_END': 45.0,  # 71 values (10.0–45.0 step 0.5)
    'ENTRY_THRESHOLD_STEP': 0.5,

    'EXIT_THRESHOLD_START': 55.0,
    'EXIT_THRESHOLD_END': 90.0,   # 71 values (55.0–90.0 step 0.5)
    'EXIT_THRESHOLD_STEP': 0.5,

    # Unused — short thresholds are derived symmetrically from long thresholds
    # so all signal DataFrames share identical column shapes (vectorbt requirement).
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
    'ENABLE_SHORTING': True, # Enables short trading for MA, RSI, MACD strategies
    # Trend filter: gates long entries to bars where close >= N-bar MA,
    # and short entries to bars where close <= N-bar MA.  This creates genuine
    # diversity between long and short conditions and produces flat periods when
    # price is in a neutral zone.  Scale with your interval:
    #   1m/5m data  → 50–200 bars    (50 bars = 50 min on 1m, 4 hrs on 5m)
    #   1h data     → 50–100 bars
    #   1D data     → 50 or 200 bars (classic 50/200-day MA filter)
    #   0           → disabled (every crossover signal fires regardless of trend)
    'TREND_FILTER_WINDOW': 50,
    # --- Position Sizing ---
    'DEFAULT_SIZE': .9,      # Use 90% of equity per trade (leaves 10% as buffer for fees/slippage)
    'DEFAULT_SIZE_TYPE': 'percent', # 'percent' is auto-converted to 'value' when shorting (vectorbt limitation); capped at 25% of INITIAL_CAPITAL to prevent leverage blowup

    # --- Stop Loss ---
    'USE_STOP_LOSS': True,     # Set to True to enable stop-loss
    'STOP_LOSS_PERCENT': 0.05, # Example: 5% stop-loss (relative to entry price)

    # --- Take Profit ---
    'USE_TAKE_PROFIT': False,    # Set to True to enable take-profit
    'TAKE_PROFIT_PERCENT': 0.10, # Example: 10% take-profit (relative to entry price)

    # --- ATR-Based / Trailing Stops ---
    'ATR_SL_WINDOW': None,       # None = use fixed %, set to e.g. 14 for ATR-based stops
    'ATR_SL_MULTIPLIER': 2.0,    # ATR multiplier for stop distance (e.g., 2× ATR)
    'USE_TRAILING_STOP': False,  # True = trailing stop instead of fixed

    # --- Simulation Frequency ---
    # IMPORTANT: DEFAULT_FREQ must match your data INTERVAL or vectorbt will produce
    # incorrect annualized metrics (Sharpe, CAGR, etc.).
    # Leave as None to auto-detect from DATA_CONFIG['INTERVAL'] via utils.freq_utils.
    # Manual overrides: 'D' = daily, 'h' = hourly, '5min' = 5-minute, '1min' = 1-minute
    'DEFAULT_FREQ': None      # None = auto-detect from INTERVAL (recommended)
}

# Configuration for MACD Strategy
# Valid combos (fast < slow) ≈ 120k from raw 38×115×27 = 117,990
STRATEGY_MACD = {
    # Fast EMA Window Range
    "FAST_WINDOW_START": 2,
    "FAST_WINDOW_END": 40,   # 38 values (2–39)
    "FAST_WINDOW_STEP": 1,

    # Slow EMA Window Range (Must be > Fast Window; combos where fast>=slow are dropped)
    "SLOW_WINDOW_START": 5,
    "SLOW_WINDOW_END": 120,  # 115 values (5–119)
    "SLOW_WINDOW_STEP": 1,

    # Signal Line EMA Window Range
    "SIGNAL_WINDOW_START": 3,
    "SIGNAL_WINDOW_END": 30,  # 27 values (3–29)
    "SIGNAL_WINDOW_STEP": 1,

    # Shorting control (specific to this strategy)
    "SHORT_ENTRIES_ENABLED": True,
    "SHORT_EXITS_ENABLED": True,
}

# Configuration for Volume Breakout Strategy
# 70 vol_windows × 19 multipliers × 80 exit_ma = 106,400 combos
STRATEGY_VOLUME_BREAKOUT = {
    # Volume lookback window
    "VOLUME_WINDOW_START": 10,
    "VOLUME_WINDOW_END": 80,   # 70 values (10–79)
    "VOLUME_WINDOW_STEP": 1,
    # Volume spike multiplier
    "VOLUME_MULTIPLIER_START": 1.2,
    "VOLUME_MULTIPLIER_END": 3.0,   # 19 values (1.2–3.0 step 0.1)
    "VOLUME_MULTIPLIER_STEP": 0.1,
    # Exit MA window
    "EXIT_MA_WINDOW_START": 10,
    "EXIT_MA_WINDOW_END": 90,   # 80 values (10–89)
    "EXIT_MA_WINDOW_STEP": 1,
    # Other settings
    "CONFIRM_PRICE_INCREASE": False,
}

# Configuration for Bollinger Bands Breakout Strategy
# 21 windows × 9 stds = 189 combos (fast, lightweight sweep)
STRATEGY_BBANDS = {
    "BBANDS_WINDOW_START": 10,
    "BBANDS_WINDOW_END": 51,
    "BBANDS_WINDOW_STEP": 2,
    "BBANDS_STD_START": 1.0,
    "BBANDS_STD_END": 3.25,
    "BBANDS_STD_STEP": 0.25,
}

# Configuration for Stochastic Crossover Strategy
# 16 k_windows × 7 d_windows = 112 combos
STRATEGY_STOCH = {
    "STOCH_K_START": 5,
    "STOCH_K_END": 21,
    "STOCH_K_STEP": 1,
    "STOCH_D_START": 3,
    "STOCH_D_END": 10,
    "STOCH_D_STEP": 1,
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