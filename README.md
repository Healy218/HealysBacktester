# Healy's Backtester

A Python backtesting framework for algorithmic trading strategies. Built on [vectorbt](https://vectorbt.dev/) for fast, vectorized simulation of thousands of parameter combinations at once.

---

## What It Does

1. Downloads OHLCV price data from Alpaca (with local caching)
2. Generates trading signals for each parameter combination in a strategy
3. Simulates all combinations simultaneously using vectorbt
4. Finds the best-performing parameter set and saves stats, trades, and plots
5. Displays results in a Dash web dashboard

---

## Project Structure

```
HealysBacktester/
├── config/
│   └── settings.py          # All configuration: symbol, dates, strategy params, fees, etc.
├── data/
│   ├── cache/               # Cached CSV downloads (auto-created)
│   ├── vbt_data_loader.py   # Downloads data from Alpaca (cache-first); Alpaca-only
│   ├── alpaca_loader.py     # Lower-level Alpaca bar loader (used by NN scripts)
│   └── data_cleaner.py      # Validates and normalizes OHLCV DataFrames
├── signals/
│   ├── ma_crossover.py      # MA crossover signal generator
│   ├── rsi_threshold.py     # RSI threshold signal generator
│   ├── macd_signals.py      # MACD crossover signal generator
│   ├── volume_breakout.py   # Volume breakout signal generator
│   └── signal_combiners.py  # (stub) Multi-strategy signal combiner
├── portfolio/
│   └── simulator.py         # Wraps vbt.Portfolio.from_signals(); handles index alignment
├── analysis/
│   ├── metrics.py           # Stats extraction, trade records, result saving orchestrator
│   └── plotting.py          # Plotly figure generators (equity curve, trades, drawdown)
├── indicators/
│   ├── moving_averages.py   # SMA/EMA wrappers
│   ├── rsi.py               # RSI wrappers
│   └── common_indicators.py # (stub) Future shared indicator library
├── utils/
│   ├── config_parser.py     # Dynamically loads settings.py as a module
│   ├── error_handling.py    # Custom exceptions + @handle_errors decorator
│   ├── file_utils.py        # Creates result dirs, saves CSVs and Plotly JSON
│   └── logging_utils.py     # Configures logging to file + console
├── scripts/
│   ├── ma_backtest.py       # Run MA crossover optimization
│   ├── rsi_backtest.py      # Run RSI threshold optimization
│   ├── macd_backtest.py     # Run MACD crossover optimization
│   ├── volume_backtest.py   # Run volume breakout optimization
│   └── ma_rsi_backtest.py   # (legacy) Combined MA + RSI strategy
├── results/                 # Timestamped output directories (auto-created)
├── logs/                    # Log files (auto-created)
├── models/                  # (experimental) ML models, not yet integrated
├── sentiment/               # (experimental) Sentiment analysis, not yet integrated
├── main.py                  # Dash web dashboard for browsing saved results
└── requirements.txt         # Python dependencies
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install vectorbt pandas numpy plotly dash dash-bootstrap-components alpaca-py
```

> The full `requirements.txt` is a complete environment dump. The core dependencies above are what you actually need.

### 2. Configure your backtest

Edit `config/settings.py`:

```python
DATA_CONFIG = {
    "SYMBOL": "AAPL",          # Ticker to backtest
    "START_DATE": "2024-01-01",
    "END_DATE": "2024-12-31",
    "INTERVAL": "1D",           # '1m', '5m', '1h', '1D', etc.
}

BACKTEST_CONFIG = {
    'INITIAL_CAPITAL': 100000.0,
    'FEES_PERCENT': 0.001,       # 0.1% per trade
    'SLIPPAGE_PERCENT': 0.0005,  # 0.05% per trade
    'USE_STOP_LOSS': True,
    'STOP_LOSS_PERCENT': 0.05,   # 5% stop loss
}
```

### 3. Run a backtest

```bash
# From the project root:
python scripts/ma_backtest.py       # Moving average crossover
python scripts/rsi_backtest.py      # RSI threshold
python scripts/macd_backtest.py     # MACD crossover
python scripts/volume_backtest.py   # Volume breakout
```

Each script runs all parameter combinations for that strategy and saves results to `results/`.

### 4. View results in the dashboard

```bash
python main.py
# Open http://127.0.0.1:8050 in your browser
```

Select a backtest run from the dropdown to see:
- Config used
- Best parameter performance summary
- Portfolio equity curve plot
- Trade entry/exit plot
- Full trade records table

---

## Strategies

### Moving Average Crossover (`ma_backtest.py`)
Buys when the fast MA crosses above the slow MA, sells on the reverse.

- **Parameter space:** All fast/slow window combinations from a configurable range (default: windows 2-142, ~9,870 combinations)
- **Config section:** `STRATEGY_MA_CROSSOVER`
- **Key settings:**
  ```python
  "MA_WINDOW_START": 2,
  "MA_WINDOW_END": 143,   # Tests windows 2 through 142
  "MA_WINDOW_STEP": 1,
  ```

### RSI Threshold (`rsi_backtest.py`)
Buys when RSI crosses below the entry threshold (oversold), sells when RSI crosses above the exit threshold (overbought).

- **Parameter space:** Combinations of RSI window × entry threshold × exit threshold
- **Config section:** `STRATEGY_RSI`
- **Supports shorting** when `ENABLE_SHORTING: True` in `BACKTEST_CONFIG`
- **Key settings:**
  ```python
  'RSI_WINDOW_START': 5, 'RSI_WINDOW_END': 35,
  'ENTRY_THRESHOLD_START': 10.0, 'ENTRY_THRESHOLD_END': 49.0,
  'EXIT_THRESHOLD_START': 51.0, 'EXIT_THRESHOLD_END': 90.0,
  ```

### MACD Crossover (`macd_backtest.py`)
Buys when the MACD line crosses above the signal line, sells on the reverse.

- **Parameter space:** Fast EMA × slow EMA × signal line EMA combinations (constraint: fast < slow)
- **Config section:** `STRATEGY_MACD`
- **Key settings:**
  ```python
  "FAST_WINDOW_START": 3, "FAST_WINDOW_END": 27,
  "SLOW_WINDOW_START": 17, "SLOW_WINDOW_END": 42,
  "SIGNAL_WINDOW_START": 3, "SIGNAL_WINDOW_END": 23,
  ```

### Volume Breakout (`volume_backtest.py`)
Buys when volume spikes above a multiple of its moving average; exits when price drops below a separate MA.

- **Parameter space:** Volume window × multiplier × exit MA window combinations
- **Config section:** `STRATEGY_VOLUME_BREAKOUT`
- **Key settings:**
  ```python
  "VOLUME_WINDOW_START": 30, "VOLUME_WINDOW_END": 60,
  "VOLUME_MULTIPLIER_START": 1.5, "VOLUME_MULTIPLIER_END": 2.0,
  "EXIT_MA_WINDOW_START": 45, "EXIT_MA_WINDOW_END": 90,
  ```

---

## Configuration Reference (`config/settings.py`)

| Section | Key | Default | Description |
|---|---|---|---|
| `DATA_CONFIG` | `SYMBOL` | `"FUBO"` | Ticker symbol |
| `DATA_CONFIG` | `START_DATE` | `"2025-03-03"` | Backtest start date |
| `DATA_CONFIG` | `END_DATE` | `"2025-04-30"` | Backtest end date |
| `DATA_CONFIG` | `INTERVAL` | `"5m"` | Bar interval (`1m`, `5m`, `1h`, `1D`) |
| `BACKTEST_CONFIG` | `INITIAL_CAPITAL` | `100000.0` | Starting cash ($) |
| `BACKTEST_CONFIG` | `FEES_PERCENT` | `0.001` | Fee per trade (0.1%) |
| `BACKTEST_CONFIG` | `SLIPPAGE_PERCENT` | `0.0005` | Slippage per trade (0.05%) |
| `BACKTEST_CONFIG` | `DEFAULT_SIZE` | `0.9` | Fraction of equity per trade (90%) |
| `BACKTEST_CONFIG` | `USE_STOP_LOSS` | `True` | Enable stop loss |
| `BACKTEST_CONFIG` | `STOP_LOSS_PERCENT` | `0.05` | Stop loss at 5% below entry |
| `BACKTEST_CONFIG` | `USE_TAKE_PROFIT` | `False` | Enable take profit |
| `BACKTEST_CONFIG` | `TAKE_PROFIT_PERCENT` | `0.10` | Take profit at 10% above entry |
| `BACKTEST_CONFIG` | `ENABLE_SHORTING` | `False` | Enable short trades (RSI only) |
| `BACKTEST_CONFIG` | `DEFAULT_FREQ` | `"D"` | vectorbt frequency string |

> **Frequency string:** Must match your data interval. Use `"T"` for minute bars, `"H"` for hourly, `"D"` for daily.

---

## How Backtesting Works (Under the Hood)

All strategy scripts follow the same 4-stage pipeline:

```
[1/4] Load & Clean Data
      vbt_data_loader.load_price_data_smart()  → Download from Alpaca (or load from cache)
      data_cleaner.clean_ohlcv_data()  → Validate columns, handle NaNs, ensure DatetimeIndex

[2/4] Generate Signals
      signals/<strategy>.generate_*_signals()
      → Returns boolean DataFrames with MultiIndex columns: one column per parameter combo
      → e.g., entries.shape = (num_bars, num_combinations)

[3/4] Run Simulation
      simulator.run_backtest()
      → Normalizes indices to TZ-naive DatetimeIndex
      → Reindexes signals to align with price data
      → Calls vbt.Portfolio.from_signals() — simulates ALL combinations simultaneously

[4/4] Analyze & Save
      portfolio.total_return().idxmax()  → Find best combination
      metrics.save_run_results()         → Save config, stats CSV, trades CSV, Plotly JSON plots
```

Results are saved to `results/<strategy>_<SYMBOL>_<timestamp>/`:
```
results/ma_crossover_FUBO_20250429_152628/
├── config_used.py            # Exact config snapshot
├── best_params_stats.csv     # Performance metrics for best combo
├── best_params_trades.csv    # Individual trade records
├── plot_portfolio_summary.json  # Equity curve (Plotly JSON)
└── plot_trades.json          # Trade entry/exit chart (Plotly JSON)
```

---

## Data Caching

Downloaded data is cached as CSV in `data/cache/` using the filename pattern:
```
<SYMBOL>_<INTERVAL>_<START_DATE>_<END_DATE>.csv
```

To force a fresh download, delete the relevant file from `data/cache/`.

> **Note on data source:** Data comes exclusively from Alpaca (set `ALPACA_API_KEY` / `ALPACA_API_SECRET` in `.env`). There is no Yahoo fallback — if Alpaca lacks credentials, doesn't support the interval, or returns no data, the load fails with a clear error rather than silently using another source.

---

## Logging

All scripts log to both the console and `logs/backtester.log`. Log level is set in:
```python
LOGGING_CONFIG = {
    "LEVEL": "INFO",
    "FILE_PATH": "logs/backtester.log"
}
```

Change to `"DEBUG"` to see verbose output including index normalization and signal reindexing steps.

---

## Known Limitations

- **Optimization metric:** Best parameters are selected by **total return only**. High-return combos may have poor Sharpe ratios or deep drawdowns. Consider using Sharpe ratio instead.
- **No walk-forward validation:** Results may be overfitted to the test period. Always validate on out-of-sample data.
- **Intraday data limits:** Alpaca's free tier caps intraday history and bar counts per request. Use daily bars for longer backtests.
- **RSI signal misalignment:** The RSI strategy uses separate DataFrames for entries/exits (different MultiIndex levels). vectorbt handles this via broadcasting, but results should be spot-checked.
- **Models and sentiment folders:** The `models/` and `sentiment/` directories are experimental stubs and are not integrated into any backtest scripts.

---

## Dependencies (Core)

| Package | Version | Purpose |
|---|---|---|
| `vectorbt` | 0.27.x | Backtesting engine, portfolio simulation, indicators |
| `pandas` | 2.2.x | Data manipulation |
| `numpy` | 2.1.x | Numerical arrays |
| `plotly` | 5.24.x | Interactive charts |
| `dash` | 3.0.x | Web dashboard |
| `dash-bootstrap-components` | 2.0.x | Dashboard styling |
| `alpaca-py` | 0.x | Alpaca market data (sole data source) |
| `ta-lib` | 0.6.x | Optional alternative indicator library |
