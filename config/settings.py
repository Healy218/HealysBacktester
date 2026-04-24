# filename: HealysBacktester/config/settings.py

# config/settings.py

# --- Data Configuration ---
DATA_CONFIG = {
    "SYMBOLS": ["SPY", "QQQ", "TSLA", "NVDA", "AAPL", "AMD"],
    "START_DATE": "2023-04-15",
    "END_DATE": "2026-04-15",
    "INTERVAL": "5m",  # Noise-reduced interval
    "DATA_PROVIDER": "Alpaca"
}

# --- Strategy Configuration ---

# MA Crossover
STRATEGY_MA_CROSSOVER = {
    # Combinations (r=2) where fast < slow: n*(n-1)/2
    # 524 windows → 524*523/2 = 137,026 combos
    "MA_WINDOW_START": 2,
    "MA_WINDOW_END": 1050,
    "MA_WINDOW_STEP": 2,
}

# RSI Threshold
# True cross-product: windows × entry_thresholds × exit_thresholds
# 26 windows × 72 entry × 72 exit = 134,784 combos
STRATEGY_RSI = {
    'RSI_WINDOW_START': 5,
    'RSI_WINDOW_END': 31,   # 26 windows (5–30)
    'RSI_WINDOW_STEP': 1,

    'ENTRY_THRESHOLD_START': 10.0,
    'ENTRY_THRESHOLD_END': 45.5,  # 72 values (10.0–45.5 step 0.5)
    'ENTRY_THRESHOLD_STEP': 0.5,

    'EXIT_THRESHOLD_START': 55.0,
    'EXIT_THRESHOLD_END': 90.5,   # 72 values (55.0–90.5 step 0.5)
    'EXIT_THRESHOLD_STEP': 0.5,

    # Unused — short thresholds are derived symmetrically from long thresholds
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

    # --- Sentiment Filter (overlay on any strategy) ---
    'SENTIMENT_FILTER_ENABLED': False,     # Set True to gate entries by sentiment
    'SENTIMENT_FILTER_THRESHOLD': 0.1,     # Min sentiment score to allow entries
    'SENTIMENT_FILTER_PROVIDER': 'alphavantage',

    # --- Simulation Frequency ---
    # IMPORTANT: DEFAULT_FREQ must match your data INTERVAL or vectorbt will produce
    # incorrect annualized metrics (Sharpe, CAGR, etc.).
    # Leave as None to auto-detect from DATA_CONFIG['INTERVAL'] via utils.freq_utils.
    # Manual overrides: 'D' = daily, 'h' = hourly, '5min' = 5-minute, '1min' = 1-minute
    'DEFAULT_FREQ': None      # None = auto-detect from INTERVAL (recommended)
}

# Configuration for MACD Strategy
# Valid combos (fast < slow) ≈ 137k from 49 fast × 121 slow × 26 signal
STRATEGY_MACD = {
    # Fast EMA Window Range
    "FAST_WINDOW_START": 2,
    "FAST_WINDOW_END": 51,   # 49 values (2–50)
    "FAST_WINDOW_STEP": 1,

    # Slow EMA Window Range (Must be > Fast Window; combos where fast>=slow are dropped)
    "SLOW_WINDOW_START": 10,
    "SLOW_WINDOW_END": 251,  # 121 values (10–250 step 2)
    "SLOW_WINDOW_STEP": 2,

    # Signal Line EMA Window Range
    "SIGNAL_WINDOW_START": 3,
    "SIGNAL_WINDOW_END": 29,  # 26 values (3–28)
    "SIGNAL_WINDOW_STEP": 1,

    # Shorting control (specific to this strategy)
    "SHORT_ENTRIES_ENABLED": True,
    "SHORT_EXITS_ENABLED": True,
}

# Configuration for Volume Breakout Strategy
# 53 vol_windows × 26 multipliers × 100 exit_ma ≈ 137,800 combos
STRATEGY_VOLUME_BREAKOUT = {
    # Volume lookback window
    "VOLUME_WINDOW_START": 5,
    "VOLUME_WINDOW_END": 111,   # 53 values (5–109 step 2)
    "VOLUME_WINDOW_STEP": 2,
    # Volume spike multiplier
    "VOLUME_MULTIPLIER_START": 1.0,
    "VOLUME_MULTIPLIER_END": 3.55,  # 26 values (1.0–3.5 step 0.1)
    "VOLUME_MULTIPLIER_STEP": 0.1,
    # Exit MA window
    "EXIT_MA_WINDOW_START": 5,
    "EXIT_MA_WINDOW_END": 105,  # 100 values (5–104)
    "EXIT_MA_WINDOW_STEP": 1,
    # Other settings
    "CONFIRM_PRICE_INCREASE": False,
}

# Configuration for Bollinger Bands Breakout Strategy
# 250 windows × 81 stds = 20,250 combos
# Note: std step 0.05 covers the practical range thoroughly — finer steps
# (e.g., 0.0073) produce near-identical bands and waste memory/compute.
STRATEGY_BBANDS = {
    "BBANDS_WINDOW_START": 3,
    "BBANDS_WINDOW_END": 503,       # 250 windows (3–502 step 2)
    "BBANDS_WINDOW_STEP": 2,
    "BBANDS_STD_START": 0.50,
    "BBANDS_STD_END": 4.505,        # 81 values (0.50–4.50 step 0.05)
    "BBANDS_STD_STEP": 0.05,
}

# Configuration for Stochastic Crossover Strategy
# True cross-product: k_windows × d_windows × oversold × overbought
# 24 × 13 × 20 × 22 ≈ 137,280 combos
STRATEGY_STOCH = {
    "STOCH_K_START": 3,
    "STOCH_K_END": 51,              # 24 windows (3–49 step 2)
    "STOCH_K_STEP": 2,
    "STOCH_D_START": 2,
    "STOCH_D_END": 15,              # 13 windows (2–14)
    "STOCH_D_STEP": 1,
    "STOCH_OVERSOLD_START": 5,
    "STOCH_OVERSOLD_END": 25,       # 20 values (5–24)
    "STOCH_OVERSOLD_STEP": 1,
    "STOCH_OVERBOUGHT_START": 70,
    "STOCH_OVERBOUGHT_END": 92,     # 22 values (70–91)
    "STOCH_OVERBOUGHT_STEP": 1,
}

# Configuration for Elliott Wave / Fibonacci Retracement Strategy
# Swing detection order × Fibonacci level × Fibonacci zone tolerance
# 20 × 225 × 30 ≈ 135,000 combos
STRATEGY_ELLIOTT = {
    "SWING_ORDER_START": 2,
    "SWING_ORDER_END": 42,          # 20 values (2–40 step 2)
    "SWING_ORDER_STEP": 2,
    "FIB_LEVEL_START": 0.050,
    "FIB_LEVEL_END": 0.950,         # 225 values (0.050–0.948 step 0.004)
    "FIB_LEVEL_STEP": 0.004,
    "FIB_TOLERANCE_START": 0.001,
    "FIB_TOLERANCE_END": 0.031,     # 30 values (0.001–0.030 step 0.001)
    "FIB_TOLERANCE_STEP": 0.001,
}

# Configuration for Sentiment Strategy
# Sweeps: smoothing_windows x entry_thresholds x exit_thresholds
# 3 windows x 10 entry x 10 exit = 300 combos (lightweight — news data is sparse)
# NOTE: VADER compound scores range [-1, 1] but daily averages typically cluster
# in [-0.15, 0.15].  Thresholds should be set accordingly.
STRATEGY_SENTIMENT = {
    "PROVIDER": "alphavantage",  # Data source: "alphavantage" or "finnhub"

    # Smoothing window (rolling mean over raw sentiment scores)
    "SENTIMENT_WINDOW_START": 1,
    "SENTIMENT_WINDOW_END": 4,   # 3 values (1-3 periods)
    "SENTIMENT_WINDOW_STEP": 1,

    # Bullish entry threshold (sentiment must cross above)
    "ENTRY_THRESHOLD_START": 0.01,
    "ENTRY_THRESHOLD_END": 0.10,  # 10 values
    "ENTRY_THRESHOLD_STEP": 0.01,

    # Bearish exit threshold (sentiment must cross below)
    "EXIT_THRESHOLD_START": -0.10,
    "EXIT_THRESHOLD_END": -0.01,  # 10 values
    "EXIT_THRESHOLD_STEP": 0.01,
}

# Configuration for Neural Network Strategy
STRATEGY_NN = {
    "LOOKBACK_WINDOW": 24, # 2 hours of history (24 * 5m)

    # Sweep Ranges (Target Returns for Triple Barrier)
    "HORIZONS": [12, 24, 48], # 1h, 2h, 4h
    "THRESHOLDS": [0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.025],

    # Dynamic Management
    "STOP_LOSS_MULT": 0.5, # Stop loss is 0.5x the profit target
    "PROBABILITY_THRESHOLD": 0.85,
    "EXIT_PROBABILITY_THRESHOLD": 0.40,  # Exit when P(up) drops below this
    "RETURN_THRESHOLD": 0.01,            # Min return for classification label

    # Training
    "EPOCHS": 15,
    "BATCH_SIZE": 512,
    "TRAIN_TEST_SPLIT": 0.8,
    "VALIDATION_SPLIT": 0.1,
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