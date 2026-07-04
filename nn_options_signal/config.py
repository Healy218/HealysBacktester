# nn_options_signal/config.py
"""Every constant for the SPY-options NN signal pipeline lives here.

Standalone module — nothing in here imports from the rest of the repo.
"""
import os
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "data_cache"
BARS_DIR = CACHE_DIR / "bars"           # bars_part_NNNN.parquet chunks
RUNS_DIR = ROOT / "runs"
REPORTS_DIR = ROOT / "reports"

CONTRACTS_PARQUET = CACHE_DIR / "contracts.parquet"
UNIVERSE_PARQUET = CACHE_DIR / "universe.parquet"
UNDERLYING_PARQUET = CACHE_DIR / "underlying_daily.parquet"
DONE_MANIFEST = CACHE_DIR / "bars_done.txt"     # resumability: one OCC ticker per line
DATASET_PARQUET = CACHE_DIR / "dataset.parquet"
RUNS_CSV = RUNS_DIR / "runs.csv"

# ── Underlyings ──────────────────────────────────────────────────────────────
# Pooled cross-sectional training: one model over all names. Low-priced tickers
# contribute few rows (strike grid vs ±3% band + premium floor) — expected.
UNDERLYINGS = ["SPY", "QQQ", "VOO", "MSFT", "META", "AMZN", "AAPL", "GOOG",
               "NVDA", "TSM", "RGTI", "MU", "AXTI", "SNDK", "SLS", "NOK", "SPCX"]

# ── Data window ──────────────────────────────────────────────────────────────
WINDOW_START = "2025-01-20"        # second Trump inauguration
WINDOW_END = "2026-07-02"          # today at build time
SPY_HISTORY_START = "2024-10-01"   # extra lookback for trailing features (~60 trading days)
# Contracts whose 7–45 DTE life overlaps the window: expirations in this range.
EXPIRY_MIN = "2025-01-27"
EXPIRY_MAX = "2026-08-15"

# ── Universe filters ─────────────────────────────────────────────────────────
DTE_MIN = 7
DTE_MAX = 45
MONEYNESS_BAND = 0.03              # strike within ±3% of spot during entry-eligible life
MIN_VOLUME = 50                    # per-day contract volume floor for panel eligibility
MIN_PREMIUM = 0.20                 # $ premium floor (avoid penny-quote noise)

# ── Costs ────────────────────────────────────────────────────────────────────
COST_PER_SIDE_PCT = 0.01           # 1% of premium per side (half-spread proxy)
COMMISSION_PER_CONTRACT = 0.65     # $ per contract per side
COST_STRESS_MULT = 2.0             # report P/L at stressed costs too
CONTRACT_MULTIPLIER = 100

# ── Labels ───────────────────────────────────────────────────────────────────
HORIZONS = [3, 5]                  # trading days held (exit earlier if DTE <= FORCE_EXIT_DTE)
FORCE_EXIT_DTE = 2
LABEL_CLIP = (-0.90, 3.00)         # winsorize fat-tailed option returns

# ── Splits (purged, time-based) ──────────────────────────────────────────────
TRAIN_START, TRAIN_END = "2025-01-20", "2025-12-19"
VAL_START, VAL_END = "2026-01-05", "2026-03-27"
TEST_START, TEST_END = "2026-04-06", "2026-07-02"

# ── IV inversion (Black-Scholes, European approx) ────────────────────────────
RISK_FREE_RATE = 0.0425
DIVIDEND_YIELD = 0.012

# ── Model / training grid ────────────────────────────────────────────────────
ARCHITECTURES = [[64, 32, 16], [32, 16]]
LEARNING_RATES = [1e-3, 3e-4]
SEEDS = [0, 1, 2, 3, 4]
DROPOUT = 0.25
L2_REG = 1e-5
BATCH_SIZE = 512
MAX_EPOCHS = 150      # full budget, no early stop; best-val epoch's weights kept
HUBER_DELTA = 0.10

# ── Backtest / signal ────────────────────────────────────────────────────────
PRED_THRESHOLD = 0.05              # long: enter if predicted net H-day return > +5%
SHORT_PRED_THRESHOLD = -0.10       # short: enter if predicted net H-day return < -10%
PRED_SPREAD_THRESHOLD = 0.15       # long-short: enter pair if pred_top - pred_bottom > 15%
POSITION_FRACTION = 0.10           # long leg: 10% of equity in premium
SHORT_POSITION_FRACTION = 0.30     # short leg: 30% of equity in margin (ATM contracts are margin-heavy)
INITIAL_CAPITAL = 100_000.0
# Naked short-option margin: premium + max(MARGIN_BASE_PCT*spot - OTM, MARGIN_MIN_PCT*basis)
MARGIN_BASE_PCT = 0.20
MARGIN_MIN_PCT = 0.10

# ── Selection guardrails (validation) ────────────────────────────────────────
# One position at a time + entry lag means a trade occupies H+2 trading days,
# capping a 58-day validation window at ~8 (h5) to ~12 (h3) trades. The
# original floor of 15 was unattainable; recalibrated to 6 before the test
# set was ever evaluated (disclosed in the final report).
MIN_TRADES = 6
MAX_DRAWDOWN_CAP = 0.40
MIN_PROFIT_FACTOR = 1.2
MIN_PASSING_SEEDS = 3              # config eligible if >= this many seeds pass

# ── API ──────────────────────────────────────────────────────────────────────
MASSIVE_BASE_URL = os.environ.get("MASSIVE_BASE_URL", "https://api.massive.com")
DOWNLOAD_WORKERS = 8
REQUEST_TIMEOUT = 30
MAX_RETRIES = 5

# Smoke mode: tiny expiry slice to validate the pipeline end-to-end quickly.
SMOKE_EXPIRY_MIN = "2025-02-01"
SMOKE_EXPIRY_MAX = "2025-03-31"


def ensure_dirs():
    for d in (CACHE_DIR, BARS_DIR, RUNS_DIR, REPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
