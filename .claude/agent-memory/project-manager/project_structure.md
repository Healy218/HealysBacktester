---
name: Project Structure
description: Full directory layout, module responsibilities, and primary entry points for HealysBacktester
type: project
---

## Entry Points
- `main.py` — Dash interactive dashboard (primary UI). Runs on 127.0.0.1:8050.
- `scripts/nn_backtest.py` — Single-ticker LSTM backtest (standalone script).
- `scripts/nn_multi_backtest.py` — Multi-ticker ensemble LSTM backtest (standalone script).
- `scripts/ma_backtest.py` — Legacy MA script (pre-dashboard era, still works).
- `scripts/rsi_backtest.py` — Legacy RSI script.
- `scanner/signal_scanner.py` — Live signal scanner against saved best params.

## Module Map
| Directory | Purpose |
|-----------|---------|
| `config/settings.py` | All strategy and backtest config dicts. Single source of truth. |
| `data/alpaca_loader.py` | Direct alpaca-py download (used by nn scripts). |
| `data/data_loader.py` | Yfinance + smart fallback loader (legacy scripts). |
| `data/vbt_data_loader.py` | vbt.AlpacaData / vbt.YFData loader (used by dashboard). |
| `data/data_cleaner.py` | OHLCV cleaning, TZ normalization, NaN fill. |
| `signals/` | One file per strategy. All return (entries, exits, short_entries, short_exits). |
| `backtests/` | Runner modules called by the dashboard. Thin wrappers around signals + chunked_runner. |
| `portfolio/simulator.py` | Central vbt.Portfolio.from_signals wrapper. Handles TZ, reindex, trend filter, ATR stops. |
| `analysis/metrics.py` | Stats extraction, extended stats, heatmap data, save_run_results orchestration. |
| `analysis/plotting.py` | All plotly figure generators (portfolio summary, trades, PnL dist, monthly returns). |
| `utils/chunked_runner.py` | Chunked simulation engine for 500k-combo sweeps. |
| `utils/param_utils.py` | Best-by-metric ranking, chunked and non-chunked paths. |
| `models/nn_model.py` | LSTM model definition + train_model (Gemini-authored). |
| `models/data_preprocessing.py` | Feature engineering, labeling (simple/triple-barrier), sequence creation. |
| `indicators/` | Thin wrappers (mostly unused by main pipeline; vbt called directly in signals/). |
| `scanner/` | Live parameter monitoring. |
| `sentiment/` | Stub only — not implemented. |

## Data Flow (Dashboard)
1. `main.py` → `backtests/run_*.py` → `vbt_data_loader` → `data_cleaner`
2. → `signals/*.py` (vectorized signal generation)
3. → `chunked_runner.simulate_and_rank` → `simulator.run_backtest`
4. → `param_utils.top5_from_portfolio` → results dict
5. `main.py` callback → `plotting.*` → display

## Data Flow (NN Scripts)
1. `scripts/nn_backtest.py` → `alpaca_loader` → `data_cleaner`
2. → `data_preprocessing.prepare_nn_data` (features, labels, sequences, scaler)
3. → `nn_model.create_model` + `train_model`
4. → `nn_signals.generate_nn_signals` → `simulator.run_backtest`
5. → `metrics.save_run_results`

**Why:** Built around vectorBT's parameter-sweep paradigm for the main strategies. NN pipeline is a separate track added later.
**How to apply:** When diagnosing integration issues, trace the data flow above to find where formats diverge.
