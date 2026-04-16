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

# MA Crossover - Updated for Optimization
STRATEGY_MA_CROSSOVER = {
    # Combinations (r=2) where fast < slow: n*(n-1)/2
    # 1001 windows → 1001*1000/2 = 500,500 combos
    "MA_WINDOW_START": 2,
    "MA_WINDOW_END": 1003,
    "MA_WINDOW_STEP": 1,
}

# RSI Threshold
# True cross-product: windows × entry_thresholds × exit_thresholds
# 26 windows × 140 entry × 140 exit = 509,600 combos
STRATEGY_RSI = {
    'RSI_WINDOW_START': 5,
    'RSI_WINDOW_END': 31,   # 26 windows (5–30)
    'RSI_WINDOW_STEP': 1,

    'ENTRY_THRESHOLD_START': 10.0,
    'ENTRY_THRESHOLD_END': 45.0,  # 140 values (10.0–45.0 step 0.25)
    'ENTRY_THRESHOLD_STEP': 0.25,

    'EXIT_THRESHOLD_START': 55.0,
    'EXIT_THRESHOLD_END': 90.0,   # 140 values (55.0–90.0 step 0.25)
    'EXIT_THRESHOLD_STEP': 0.25,

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
    'SENTIMENT_FILTER_PROVIDER': 'finnhub',

    # --- Simulation Frequency ---
    # IMPORTANT: DEFAULT_FREQ must match your data INTERVAL or vectorbt will produce
    # incorrect annualized metrics (Sharpe, CAGR, etc.).
    # Leave as None to auto-detect from DATA_CONFIG['INTERVAL'] via utils.freq_utils.
    # Manual overrides: 'D' = daily, 'h' = hourly, '5min' = 5-minute, '1min' = 1-minute
    'DEFAULT_FREQ': None      # None = auto-detect from INTERVAL (recommended)
}

# Configuration for MACD Strategy
# Valid combos (fast < slow) ≈ 522k from 68 fast × 195 slow × 47 signal
STRATEGY_MACD = {
    # Fast EMA Window Range
    "FAST_WINDOW_START": 2,
    "FAST_WINDOW_END": 70,   # 68 values (2–69)
    "FAST_WINDOW_STEP": 1,

    # Slow EMA Window Range (Must be > Fast Window; combos where fast>=slow are dropped)
    "SLOW_WINDOW_START": 5,
    "SLOW_WINDOW_END": 200,  # 195 values (5–199)
    "SLOW_WINDOW_STEP": 1,

    # Signal Line EMA Window Range
    "SIGNAL_WINDOW_START": 3,
    "SIGNAL_WINDOW_END": 50,  # 47 values (3–49)
    "SIGNAL_WINDOW_STEP": 1,

    # Shorting control (specific to this strategy)
    "SHORT_ENTRIES_ENABLED": True,
    "SHORT_EXITS_ENABLED": True,
}

# Configuration for Volume Breakout Strategy
# 105 vol_windows × 51 multipliers × 95 exit_ma ≈ 508,725 combos
STRATEGY_VOLUME_BREAKOUT = {
    # Volume lookback window
    "VOLUME_WINDOW_START": 5,
    "VOLUME_WINDOW_END": 110,   # 105 values (5–109)
    "VOLUME_WINDOW_STEP": 1,
    # Volume spike multiplier
    "VOLUME_MULTIPLIER_START": 1.0,
    "VOLUME_MULTIPLIER_END": 3.55,  # 51 values (1.0–3.5 step 0.05)
    "VOLUME_MULTIPLIER_STEP": 0.05,
    # Exit MA window
    "EXIT_MA_WINDOW_START": 5,
    "EXIT_MA_WINDOW_END": 100,  # 95 values (5–99)
    "EXIT_MA_WINDOW_STEP": 1,
    # Other settings
    "CONFIRM_PRICE_INCREASE": False,
}

# Configuration for Bollinger Bands Breakout Strategy
# 500 windows × 1000 stds = 500,000 combos
STRATEGY_BBANDS = {
    "BBANDS_WINDOW_START": 3,
    "BBANDS_WINDOW_END": 503,       # 500 windows (3–502)
    "BBANDS_WINDOW_STEP": 1,
    "BBANDS_STD_START": 0.50,
    "BBANDS_STD_END": 4.50,         # 1000 values (0.50–4.496 step 0.004)
    "BBANDS_STD_STEP": 0.004,
}

# Configuration for Stochastic Crossover Strategy
# True cross-product: k_windows × d_windows × oversold × overbought
# 47 × 13 × 30 × 27 ≈ 494,910 combos
STRATEGY_STOCH = {
    "STOCH_K_START": 3,
    "STOCH_K_END": 50,              # 47 windows (3–49)
    "STOCH_K_STEP": 1,
    "STOCH_D_START": 2,
    "STOCH_D_END": 15,              # 13 windows (2–14)
    "STOCH_D_STEP": 1,
    "STOCH_OVERSOLD_START": 5,
    "STOCH_OVERSOLD_END": 35,       # 30 values (5–34)
    "STOCH_OVERSOLD_STEP": 1,
    "STOCH_OVERBOUGHT_START": 65,
    "STOCH_OVERBOUGHT_END": 92,     # 27 values (65–91)
    "STOCH_OVERBOUGHT_STEP": 1,
}

# Configuration for Elliott Wave / Fibonacci Retracement Strategy
# Swing detection order × Fibonacci level × Fibonacci zone tolerance
# 34 × 450 × 33 ≈ 504,900 combos
STRATEGY_ELLIOTT = {
    "SWING_ORDER_START": 2,
    "SWING_ORDER_END": 36,          # 34 values (2–35)
    "SWING_ORDER_STEP": 1,
    "FIB_LEVEL_START": 0.050,
    "FIB_LEVEL_END": 0.950,         # 450 values (0.050–0.948 step 0.002)
    "FIB_LEVEL_STEP": 0.002,
    "FIB_TOLERANCE_START": 0.001,
    "FIB_TOLERANCE_END": 0.034,     # 33 values (0.001–0.033 step 0.001)
    "FIB_TOLERANCE_STEP": 0.001,
}

# Configuration for Sentiment Strategy
# Sweeps: smoothing_windows x entry_thresholds x exit_thresholds
# 7 windows x 10 entry x 10 exit = 700 combos (lightweight — news data is sparse)
STRATEGY_SENTIMENT = {
    "PROVIDER": "finnhub",  # Data source (add more in sentiment_data_loader.py)

    # Smoothing window (rolling mean over raw sentiment scores)
    "SENTIMENT_WINDOW_START": 1,
    "SENTIMENT_WINDOW_END": 8,   # 7 values (1-7 periods)
    "SENTIMENT_WINDOW_STEP": 1,

    # Bullish entry threshold (sentiment must cross above)
    "ENTRY_THRESHOLD_START": 0.05,
    "ENTRY_THRESHOLD_END": 0.50,  # 10 values
    "ENTRY_THRESHOLD_STEP": 0.05,

    # Bearish exit threshold (sentiment must cross below)
    "EXIT_THRESHOLD_START": -0.50,
    "EXIT_THRESHOLD_END": -0.05,  # 10 values
    "EXIT_THRESHOLD_STEP": 0.05,
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