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

# ── Universe / window / splits (v2: nn_meta-owned, decoupled from the
#    completed nn_options_signal experiment) ──────────────────────────────────
# Window start is bounded by Massive's rolling 2-year aggregates entitlement
# (verified 2026-07-05: data begins at today-2y exactly). One week of margin
# because the boundary rolls forward while multi-day downloads run. Data
# behind the boundary survives ONLY in our parquet caches — download early.
HISTORY_START = "2024-04-01"               # underlying warmup (Alpaca, unbounded)
WINDOW_START, WINDOW_END = "2024-07-14", "2026-07-02"
TRAIN_START, TRAIN_END = "2024-07-14", "2025-12-19"
# val/test identical to v1 so before/after comparisons stay clean:
VAL_START, VAL_END = "2026-01-05", "2026-03-27"
TEST_START, TEST_END = "2026-04-06", "2026-07-02"

# v1's 17 names + 39 liquid adds (thin names auto-skip at freeze time).
UNDERLYINGS = [
    # v1
    "SPY", "QQQ", "VOO", "MSFT", "META", "AMZN", "AAPL", "GOOG", "NVDA",
    "TSM", "RGTI", "MU", "AXTI", "SNDK", "SLS", "NOK", "SPCX",
    # mega/large caps
    "TSLA", "AMD", "NFLX", "AVGO", "INTC", "QCOM", "ORCL", "CRM", "COST",
    "HD", "WMT", "DIS", "UNH", "LLY", "PFE", "JPM", "BAC", "GS", "XOM",
    "CVX", "BA", "UBER", "F", "T",
    # high-IV retail favorites
    "PLTR", "COIN", "MSTR", "SMCI", "HOOD", "MARA", "GME",
    # ETFs
    "IWM", "DIA", "GLD", "TLT", "SMH", "XLE", "XLF", "ARKK",
]

# Contract crawl / universe filter (same criteria as nn_options_signal)
EXPIRY_MIN, EXPIRY_MAX = "2024-07-21", "2026-08-15"
DTE_MIN, DTE_MAX = _nos.DTE_MIN, _nos.DTE_MAX
MONEYNESS_BAND = _nos.MONEYNESS_BAND
MIN_VOLUME, MIN_PREMIUM = _nos.MIN_VOLUME, _nos.MIN_PREMIUM
DOWNLOAD_WORKERS = 16                      # options tier ~120/s tolerates this
REQUEST_TIMEOUT, MAX_RETRIES = _nos.REQUEST_TIMEOUT, _nos.MAX_RETRIES
MASSIVE_BASE_URL = _nos.MASSIVE_BASE_URL

# nn_meta-owned data cache (nn_options_signal's cache is no longer read)
CONTRACTS_PARQUET = DATA_CACHE / "contracts.parquet"
UNIVERSE_PARQUET = DATA_CACHE / "universe.parquet"
UNDERLYING_DAILY_PARQUET = DATA_CACHE / "underlying_daily.parquet"
BARS_DAILY_DIR = DATA_CACHE / "bars_daily"
DONE_MANIFEST = DATA_CACHE / "bars_done.txt"
SURFACE_DATASET_PARQUET = DATA_CACHE / "surface_daily.parquet"

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

# ── Student (Phase F: teacher→student standalone signal NN) ──────────────────
STUDENT_DATASET_PARQUET = ARTIFACTS / "student_dataset.parquet"
STUDENT_RUNS_CSV = RUNS_DIR / "runs_student.csv"
STUDENT_ARCH = [64, 32]
STUDENT_LRS = [1e-3, 3e-4]
CLONE_EPOCHS = 40
FINETUNE_EPOCHS = 80
FINETUNE_LR_SCALE = 0.3                    # fine-tune at a fraction of the clone LR
# Stage-2 counterfactual relabeling weights (per-bar sample weights):
STUDENT_WIN_WEIGHT_CLIP = 1.0              # win bars: weight = clip(net_return, 0, this)
STUDENT_LOSE_WEIGHT_CLIP = 1.0             # loss bars → FLAT label, weight = clip(|net|, 0, this)
STUDENT_FLAT_WEIGHT = 0.10                 # bars outside any teacher trade
STUDENT_MIN_STATE_BARS = 2                 # hysteresis: state must persist N bars
# Clone-parity go/no-go: student val option return must be within this many
# percentage points of the teacher's (or better) to proceed to fine-tuning.
CLONE_PARITY_TOLERANCE = 0.15


def ensure_dirs() -> None:
    for d in (DATA_CACHE, BARS_DAILY_DIR, ARTIFACTS, RUNS_DIR, REPORTS_DIR,
              MODEL_FINAL_DIR):
        d.mkdir(parents=True, exist_ok=True)
