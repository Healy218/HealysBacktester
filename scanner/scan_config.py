# scanner/scan_config.py
#
# Configure which symbols/strategies/params to scan here.
#
# HOW TO USE:
#   1. Run a backtest in the dashboard.
#   2. Note the "Parameters" column for your top result, e.g. "fast=10, slow=50".
#   3. Add an entry below with those exact values.
#   4. Run:  python -m scanner.signal_scanner
#
# STRATEGY OPTIONS:  "ma" | "rsi" | "macd" | "volume"
#
# PARAM KEYS PER STRATEGY:
#   ma:     fast_window (int), slow_window (int)
#   rsi:    rsi_window (int), entry_threshold (float), exit_threshold (float)
#   macd:   fast_window (int), slow_window (int), signal_window (int)
#   volume: volume_window (int), volume_multiplier (float), exit_ma_window (int)

SCANS = [
    # --- Examples (uncomment and edit with your actual best-param values) ---

    # {
    #     "strategy": "ma",
    #     "symbol": "SPY",
    #     "interval": "1D",
    #     "params": {"fast_window": 10, "slow_window": 50},
    # },
    # {
    #     "strategy": "rsi",
    #     "symbol": "FUBO",
    #     "interval": "5m",
    #     "params": {"rsi_window": 14, "entry_threshold": 30.0, "exit_threshold": 70.0},
    # },
    # {
    #     "strategy": "macd",
    #     "symbol": "AAPL",
    #     "interval": "1D",
    #     "params": {"fast_window": 12, "slow_window": 26, "signal_window": 9},
    # },
    # {
    #     "strategy": "volume",
    #     "symbol": "SPY",
    #     "interval": "1D",
    #     "params": {"volume_window": 20, "volume_multiplier": 1.5, "exit_ma_window": 50},
    # },
]
