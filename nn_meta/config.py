# nn_meta/config.py
"""Constants for the meta-labeling pipeline.

Date windows, splits, and cost constants are REUSED from nn_options_signal's
config so both NN experiments share one data regime and one purge protocol.
Everything nn_meta-specific (15m interval, DTE grid, baseline sweep, meta-model
grid) lives here.
"""
from pathlib import Path

from nn_options_signal import config as _nos

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
DATA_CACHE = ROOT / "data_cache"           # 15m caches (underlying + option bars)
ARTIFACTS = ROOT / "artifacts"             # baseline spec, meta dataset
RUNS_DIR = ROOT / "runs"
REPORTS_DIR = ROOT / "reports"
MODEL_FINAL_DIR = ROOT / "model_final"

UNDERLYING_15M_PARQUET = DATA_CACHE / "underlying_15m.parquet"
BASELINE_SPEC_JSON = ARTIFACTS / "baseline_spec.json"
META_DATASET_PARQUET = ARTIFACTS / "meta_dataset.parquet"
RUNS_CSV = RUNS_DIR / "runs.csv"

# ── Universe / window / splits (shared with nn_options_signal) ───────────────
UNDERLYINGS = _nos.UNDERLYINGS
HISTORY_START = _nos.SPY_HISTORY_START     # extra lookback for indicator warmup
WINDOW_START, WINDOW_END = _nos.WINDOW_START, _nos.WINDOW_END
TRAIN_START, TRAIN_END = _nos.TRAIN_START, _nos.TRAIN_END
VAL_START, VAL_END = _nos.VAL_START, _nos.VAL_END
TEST_START, TEST_END = _nos.TEST_START, _nos.TEST_END

# Daily surface features come from the completed nn_options_signal panel.
SURFACE_DATASET_PARQUET = _nos.DATASET_PARQUET

# ── Interval / execution ─────────────────────────────────────────────────────
INTERVAL = "15m"
# DTE grid for label execution — the cached universe covers 7–45 DTE, so the
# dashboard's 1/5-DTE variants are not available offline.
DTE_GRID = [10, 30, 45]

# Same cost constants the equity simulator applies (utils/runner_utils.py).
FEES_PERCENT = 0.001
SLIPPAGE_PERCENT = 0.0005
COST_STRESS_MULT = _nos.COST_STRESS_MULT

# Executor caps for label generation (dashboard defaults are per-run guards;
# label building must execute the full timeline).
EXEC_CONFIG = {
    "TARGET_DELTA": 0.50,
    "MONEYNESS": 0.0,
    "MAX_ROLLS_PER_TRADE": 60,
    "MAX_FILLS_PER_VARIANT": 100_000,
}

# ── Baseline freeze (Phase B) ────────────────────────────────────────────────
# MA sweep windows are in BARS (26 RTH bars per day at 15m).
MA_WINDOW_START, MA_WINDOW_END, MA_WINDOW_STEP = 2, 143, 2
ENABLE_SHORTING = True
# Prefer the best-Sharpe param set whose signal frequency stays tradable:
# options costs at 15m punish overtrading.
TRADES_PER_DAY_CEILING = 2.0
MIN_TRAIN_TRADES = 30                      # combos below this are not freezable
MAX_SIGNALS_PER_NAME = 2_000               # sanity guard for label execution

# Frozen SNAPSHOT of the dashboard BACKTEST_CONFIG (config/settings.py as of
# 2026-07-04). Pinned here so the baseline definition cannot drift if the
# dashboard settings change; consumed via utils.runner_utils.sim_kwargs().
SIM_CONFIG = {
    "INITIAL_CAPITAL": 100_000.0,
    "FEES_PERCENT": FEES_PERCENT,
    "SLIPPAGE_PERCENT": SLIPPAGE_PERCENT,
    "ENABLE_SHORTING": ENABLE_SHORTING,
    "TREND_FILTER_WINDOW": 50,
    "DEFAULT_SIZE": 0.9,
    "DEFAULT_SIZE_TYPE": "percent",
    "USE_STOP_LOSS": True,
    "STOP_LOSS_PERCENT": 0.05,
    "USE_TAKE_PROFIT": False,
    "TAKE_PROFIT_PERCENT": 0.10,
    "ATR_SL_WINDOW": None,
    "ATR_SL_MULTIPLIER": 2.0,
    "USE_TRAILING_STOP": False,
    "ATR_POSITION_SIZING": False,
    "RISK_PER_TRADE": 0.01,
    "DEFAULT_FREQ": None,                  # auto-detect from INTERVAL
}

# Fraction of equity allocated to each option position when compounding
# per-trade returns into an equity curve (same convention as nn_options_signal).
POSITION_FRACTION = 0.10

# ── Meta-model / training grid (Phase D) ─────────────────────────────────────
ARCHITECTURES = [[64, 32], [32, 16]]
LEARNING_RATES = [1e-3, 3e-4]
SEEDS = [0, 1, 2, 3, 4]
DROPOUT = _nos.DROPOUT
L2_REG = _nos.L2_REG
BATCH_SIZE = 256
MAX_EPOCHS = _nos.MAX_EPOCHS
SAMPLE_WEIGHT_CLIP = 1.0                   # weight = clip(|net_return|, 0, this)

# ── Selection guardrails (validation only; gate = beat the frozen baseline) ──
KEEP_THRESHOLDS = [0.50, 0.55, 0.60]       # P(win) needed to keep a proposal
MIN_KEPT_TRADES = 10
MAX_DRAWDOWN_CAP = 0.40
MIN_PASSING_SEEDS = 3


def ensure_dirs() -> None:
    for d in (DATA_CACHE, ARTIFACTS, RUNS_DIR, REPORTS_DIR, MODEL_FINAL_DIR):
        d.mkdir(parents=True, exist_ok=True)
