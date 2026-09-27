# Current status — September 25, 2026

**V7-1 and V7-2 are complete; V7-3 is active.** All 591 securities and 1,773
5/15/30 proposal stores passed the deep audit. The full causal daily/market
context adds 667,239 rows and passed 1,182 historical-prefix replays. The first
V7-3 demand pilot processed MTUM's 29,843 proposals into 3,552 quote/trade
requests across 76 contracts. All 591 securities remain in scope.

The catalog, daily build and first demand pilot have finished. No background
V7 build is running. Next: a resumable all-security demand scheduler, measured
request union, dated references and targeted option-path captures. Training
remains gated. See [the session evidence](docs/reviews/2026-09-25-v7-2-complete-and-v7-3-start.md),
[TODO](TODO.md) and [HANDOFF](HANDOFF.md) for exact paths and continuation.

V5 remains the server expert and the existing V6 simulator remains separate
from the fresh Alpaca paper state. The guarded Alpaca bridge is implemented;
fresh scanning and order submission are disabled, and no broker orders have
been sent. V6, Stonks and incubator runtimes were unchanged in this V7 session.
Full regression suite: 2,401 tests and 18 subtests passed.

# Prior operational checkpoint (historical)

V5 is the sole active server expert. V6 remains in experimental paper mode on
the home/V6 checkout; v3, v31 and v4 are retired and their server artifacts
have been archived and removed. The Stonks dashboard publishes the V6 forward
ledger, corrected $10,000 broker-style projection, Research, Training and FA
summaries as read-only Firestore observations.
Expiry rolls trigger 15 minutes before each option's final regular session
close; weights, entry selection, sizing and strategy exits remain frozen.
The actual-1–9-DTE campaign `v6-short-dte-20260914-now` is historical and
preserved for research; the current work is the V7 5/15/30 catalog build. Read
[HANDOFF](HANDOFF.md) and [TODO](TODO.md) for exact deployment state and next
steps; [the activation review](docs/reviews/2026-09-14-v6-forward-activation.md)
records validation and first-session limits. No broker orders are placed.

# September 5 audit and merge update (historical)

The user directed merging the review fixes into `main`, continuing in
`/home/healy/Coding/HealysBacktester`, and doing the TradingView work next,
before rebuilding the research artifacts. Integration validation passed: 642 tests and 18 subtests;
the 535-test count in the preserved notes is the pre-merge result. A local
merge does not deploy the server or launch a freeze/build/training campaign.

The September 5 audit repairs use feature/build contract `2026-09-05-causal-v2`.
Pre-audit freezes, partial checkpoints, rows, marks and bundles must be rebuilt
and validated under that contract; preserve existing files as historical
artifacts, and do not relabel them to bypass verification. Historical returns
and gate verdicts below are not corrected performance evidence. Evaluation
with a globally frozen proposal generator is restricted to periods after its
optimization horizon; it is conditional on that generator, not end-to-end
fold-local refreezing.

The full onboarding document below is retained for continuity. Its older
status claims, hard two-year entitlement limit and present-day-only universe
limitation are historical: paid data upgrades and PIT membership are now
implemented. Live components send alerts and maintain paper records; they do
not place broker orders. v6 retains v5's raw cache/window with separate
versioned artifacts; safe reuse requires matching current provenance and
complete rows/marks. See [current tasks](TODO.md), [handoff](HANDOFF.md), and
[the v7 real-time contract](docs/specs/REALTIME_SPEC.md).

See [audit remediation](docs/reviews/2026-09-05-remediation.md) and the
[original audit](docs/reviews/2026-09-05-adversarial-audit.md) for implemented
repairs and migration requirements.

---

# Healy's Backtester

What started as a [vectorbt](https://vectorbt.dev/) parameter-sweep framework for equity strategies has grown into an **options meta-labeling research pipeline**: a neural network that scores strategy-proposed option trades (P(win)), trained and evaluated under a strict point-in-time, purged, walk-forward contract, and deployed as a live alert scanner.

The repo therefore has two layers:

- **Layer 1 — vectorbt strategy sweeps** (`scripts/`, `signals/`, `portfolio/`, `main.py`): the original framework — fast vectorized backtests of thousands of MA/RSI/MACD/volume parameter combinations on equities, browsed in a Dash dashboard. Still works; documented in full below.
- **Layer 2 — the options meta-labeling pipeline** (`nn_meta/`, `nn_options_signal/`, `v3/`, `fa/`): the project's current center of gravity. Proposal strategies emit candidate option trades; a meta-classifier decides which to keep; everything is evaluated portfolio-level, out-of-fold, with costs, against a boring baseline.

> **New here? Read [`CLAUDE.md`](CLAUDE.md) first** — it defines the documentation system: [`ROADMAP.md`](ROADMAP.md) for overall goals, [`TODO.md`](TODO.md) for the current phase, [`HANDOFF.md`](HANDOFF.md) for session state, [`DOCUMENTATION.md`](DOCUMENTATION.md) for conventions/traps/ops. Design specs live in [`docs/specs/`](docs/specs/) — [`V3_SPEC.md`](docs/specs/V3_SPEC.md), [`V4_OUTLINE.md`](docs/specs/V4_OUTLINE.md) (+ [`V4_SMOKE_TEST.md`](docs/specs/V4_SMOKE_TEST.md)), [`FA_SPEC.md`](docs/specs/FA_SPEC.md).

---

## Layer 2: The Research Pipeline (current focus)

The operational system does **not** parameter-sweep equities — it trades options via a two-stage design:

1. **Proposal strategies** (RSI/MACD/MA/squeeze/TV-rating, per pool) each emit candidate option trades at frozen params/DTE — the "take everything" mechanical baseline.
2. **A meta-classifier** (`nn_meta/`) scores each proposal's P(win) and keeps only those clearing a validation-selected threshold, run through a shared slot portfolio.

Every generation must **beat the boring baseline** (a LightGBM tree and an underlying buy-&-hold basket) out-of-fold, ex-outliers, with costs — or it doesn't ship.

| Subsystem | What it is |
|---|---|
| `nn_options_signal/` | Standalone options-signal NN (earlier experiment; feeds intuition for the meta approach). |
| `nn_meta/` | **The meta-labeling pipeline.** Build dataset → freeze baseline → train ensemble → nested walk-forward select. Pools: v2 / v3 (7-strategy TV pool) / v31 (118-symbol at-scale). Live scoring in `nn_meta/live/`. |
| `v3/` | At-scale data layer: 120-symbol universe, Massive/Polygon flat-files option bars, TV indicator library, GBT baseline. |
| `fa/` | Fundamental/attention **discovery loop**: raw social/news/filing collectors → entity resolution → attention-velocity scores → frozen monthly rankings → forward-return-tracked graduation into the universe. |
| `nn_meta/live/` | Live alert scanner (Telegram), point-in-time scorer, and the v4 parity/state infrastructure. |

### v4 — causal validation (active research line)

`codex/v4-causal-validation` (see [`V4_OUTLINE.md`](docs/specs/V4_OUTLINE.md)) hardens the evaluation contract before the next training generation: explicit `available_at` feature timing, exit-time purging + embargo, nested per-fold model/threshold selection, mark-to-market option accounting, fold-local probability **calibration**, **deflated Sharpe / PBO** multiple-testing control, a score-decile **inversion diagnostic**, HAR-RV/GARCH volatility baselines, and an offline↔online feature-parity gate. It is research-in-progress — its promotion gates are not yet passed.

Typical layer-2 commands (options pipeline, not the equity scripts):

```bash
NN_META_POOL=v3  python -m nn_meta.build_meta_dataset   # assemble the labeled dataset
NN_META_POOL=v3  python -m nn_meta.walkforward_meta      # purged walk-forward verdict
NN_META_POOL=v31 python -m nn_meta.v4_evaluate --ablation --seeds 0,1,2,3,4 --epochs 60 --gbt-estimators 600
python -m pytest tests/ -q                               # full suite (self-contained fixtures)
```

---

## Project Structure

> Below is the **Layer 1** (vectorbt equity-sweep) structure. Layer-2 subsystems live in `nn_meta/`, `nn_options_signal/`, `v3/`, `fa/`, and `options/` (see the table above and the spec docs).

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

## Quick Start (Layer 1 — equity sweeps)

> For the Layer-2 options pipeline, install the full `requirements.txt` (TensorFlow, LightGBM, etc.) and use the `nn_meta` / `v4_evaluate` commands shown above.

### 1. Install dependencies

```bash
pip install vectorbt pandas numpy plotly dash dash-bootstrap-components alpaca-py
```

> The above is enough for the equity sweep scripts. The full `requirements.txt` adds the Layer-2 ML stack.

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

**Layer 1 (equity vectorbt sweeps):**
- **Optimization metric:** Best parameters are selected by **total return only** — high-return combos may have poor Sharpe or deep drawdowns.
- **No walk-forward validation *in this layer*:** the sweep scripts pick the best in-sample combo and may overfit the test period. (Layer 2's `nn_meta` pipeline *does* use purged, embargoed, nested walk-forward — that's the whole point of it.)
- **RSI signal misalignment:** entries/exits use separate MultiIndex DataFrames; vectorbt broadcasts them, but spot-check results.

**Layer 2 (options meta-labeling):**
- **Options history:** ~2 years of 15-minute option bars (Massive/Polygon entitlement-gated). Longer underlying history feeds longer-window features only.
- **Survivorship bias:** the universe is a present-day symbol list until a point-in-time constituent source exists.
- **v4 not yet validated:** the causal-validation gates in `docs/specs/V4_OUTLINE.md` are not all passed; v3.1-at-scale is ROBUST-but-outlier-fragile, not a clear upgrade over live v3 (see `ROADMAP.md`).
- **`models/` and `sentiment/`:** early experimental stubs, not wired into the meta pipeline (sentiment is lexicon-level; transformer scoring is a v4 backlog item).

---

## Dependencies (Core)

Full pins are in `requirements.txt`; a `pip freeze` snapshot is `requirements.lock.txt`. Data sources: **Alpaca** (equities, Layer 1) and **Massive/Polygon** (options bars + flat-files, Layer 2).

| Package | Version | Purpose |
|---|---|---|
| `pandas` | 2.2.3 | Data manipulation |
| `numpy` | 1.26.4 | Numerical arrays (pinned <2 for TF 2.16) |
| `vectorbt` | 0.27.2 | Layer-1 backtesting engine + indicators |
| `numba` | 0.61.2 | vectorbt JIT dependency |
| `tensorflow` | 2.16.2 | Meta-classifier MLP ensemble (Layer 2) |
| `lightgbm` | latest | GBT boring-baseline gate (Layer 2) |
| `scikit-learn` / `scipy` | latest | Metrics + GARCH(1,1) MLE (v4 vol baselines) |
| `alpaca-py` | 0.x | Alpaca market data |
| `pyarrow` / `boto3` | latest | Parquet cache + Massive flat-files S3 ingestion |
| `plotly` / `dash` / `dash-bootstrap-components` | — | Layer-1 dashboard |
