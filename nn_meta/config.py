# nn_meta/config.py
"""Constants for the meta-labeling pipeline.

Date windows, splits, and cost constants are REUSED from nn_options_signal's
config so both NN experiments share one data regime and one purge protocol.
Everything nn_meta-specific (15m interval, DTE grid, baseline sweep, meta-model
grid) lives here.
"""
import os
from pathlib import Path

from nn_options_signal import config as _nos

# ── Strategy-pool switch ─────────────────────────────────────────────────────
# NN_META_POOL=v3 selects the extended TV-strategy pool AND suffixes every
# artifact directory (_v3), so a v3 retrain can never clobber the deployed
# v2 spec/models. Default (unset) is the live v2 behavior, bit-for-bit.
POOL = os.environ.get("NN_META_POOL", "v2")
_SUF = "" if POOL == "v2" else f"_{POOL}"

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
DATA_CACHE = ROOT / "data_cache"           # shared: bars are pool-independent
ARTIFACTS = ROOT / f"artifacts{_SUF}"      # baseline spec, meta dataset
RUNS_DIR = ROOT / f"runs{_SUF}"
REPORTS_DIR = ROOT / f"reports{_SUF}"
MODEL_FINAL_DIR = ROOT / f"model_final{_SUF}"

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
# Full dashboard DTE grid. 1/5-DTE selections pick the nearest available
# expiration from the cached universe (near-expiry bars are the most liquid);
# short DTEs roll while the proposal stays on, exactly like the overlay.
DTE_GRID = [1, 5, 10, 30, 45]

# ── Proposal engines (v2.1: every offline-backtestable built-in strategy) ────
# Sentiment is excluded — it requires a live news feed. Sweep grids are
# deliberately coarser than the dashboard's: the freeze runs 6 sweeps × 56
# names (× again per walk-forward fold), so each grid is kept to ~10^2-10^4
# combos. Signal semantics come from the same signals/* generators.
# v2.2: leaner pool — dropped bbands/stoch/elliott (mostly noise proposers that
# diluted the model in v2.1's walk-forward); keep the four cleanest signals.
# The deployed v2.2 ensemble's feature schema (strat_* one-hots, scaler) is
# frozen to the V2 list; the V3 pool trains only under NN_META_POOL=v3 into
# the _v3 artifact dirs. The scanner switches pools when a v3 walk-forward
# earns it.
PROPOSAL_STRATEGIES_V2 = ["ma", "macd", "rsi", "volume"]
PROPOSAL_STRATEGIES_V3 = PROPOSAL_STRATEGIES_V2 + ["supertrend", "tv_rating",
                                                   "squeeze"]
PROPOSAL_STRATEGIES = (PROPOSAL_STRATEGIES_V3 if POOL == "v3"
                       else PROPOSAL_STRATEGIES_V2)
SWEEP_GRIDS = {
    "ma":      {"windows": (2, 143, 2)},
    "rsi":     {"window": (7, 29, 7), "entry": (20.0, 41.0, 5.0), "exit": (60.0, 81.0, 5.0)},
    "macd":    {"fast": (6, 27, 6), "slow": (18, 43, 6), "signal": (5, 20, 7)},
    "bbands":  {"window": (10, 51, 10), "std": (1.5, 3.1, 0.5)},
    "stoch":   {"k": (5, 21, 5), "d": (3, 10, 3), "oversold": (20, 21, 1), "overbought": (80, 81, 1)},
    "volume":  {"vol_window": (30, 61, 10), "vol_mult": (1.5, 2.1, 0.25), "exit_ma": (45, 91, 15)},
    "elliott": {"swing": (4, 17, 4), "fib": (0.382, 0.62, 0.118), "tol": (0.01, 0.021, 0.01)},
    "supertrend": {"window": (7, 15, 3), "mult": (2.0, 4.1, 0.5)},
    "tv_rating":  {"entry": (0.1, 0.51, 0.2), "exit": (-0.3, -0.09, 0.2)},
    "squeeze":    {"bb_mult": (1.5, 2.6, 0.5), "kc_mult": (1.0, 2.1, 0.5)},
}

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

# ── Sector groups (static one-hot context; hand-maintained) ──────────────────
SECTOR_GROUPS = ["idx_etf", "sec_etf", "tech", "semis", "fin", "crypto",
                 "defensive", "cyclical", "spec"]
SECTOR_MAP = {
    "SPY": "idx_etf", "QQQ": "idx_etf", "VOO": "idx_etf", "IWM": "idx_etf",
    "DIA": "idx_etf",
    "SMH": "sec_etf", "XLE": "sec_etf", "XLF": "sec_etf", "ARKK": "sec_etf",
    "GLD": "sec_etf", "TLT": "sec_etf",
    "MSFT": "tech", "META": "tech", "AMZN": "tech", "AAPL": "tech",
    "GOOG": "tech", "ORCL": "tech", "CRM": "tech", "NFLX": "tech",
    "UBER": "tech", "PLTR": "tech", "TSLA": "tech",
    "NVDA": "semis", "AVGO": "semis", "QCOM": "semis", "INTC": "semis",
    "AMD": "semis", "TSM": "semis", "MU": "semis", "SNDK": "semis",
    "SMCI": "semis", "AXTI": "semis",
    "JPM": "fin", "BAC": "fin", "GS": "fin",
    "COIN": "crypto", "MSTR": "crypto", "MARA": "crypto", "HOOD": "crypto",
    "UNH": "defensive", "LLY": "defensive", "PFE": "defensive",
    "WMT": "defensive", "COST": "defensive", "T": "defensive",
    "NOK": "defensive",
    "XOM": "cyclical", "CVX": "cyclical", "BA": "cyclical", "HD": "cyclical",
    "F": "cyclical", "DIS": "cyclical",
    "RGTI": "spec", "SLS": "spec", "SPCX": "spec", "GME": "spec",
}

# ── Labels (v2.1) ─────────────────────────────────────────────────────────────
# win    : net option return > 0
# excess : net option return > holding the underlying long over the same window
LABEL_TYPES = ["win", "excess"]

# ── Meta-model / training grid (Phase D) ─────────────────────────────────────
ARCHITECTURES = [[64, 32], [32, 16]]
LEARNING_RATES = [1e-3, 3e-4]
# v2.2: 40 seeds (was 5) — a 40-model ensemble smooths the wide per-seed test
# dispersion (-3% to +117%) that made v2.1 fragile in walk-forward.
SEEDS = list(range(40))
DROPOUT = _nos.DROPOUT
L2_REG = _nos.L2_REG
BATCH_SIZE = 256
MAX_EPOCHS = _nos.MAX_EPOCHS
SAMPLE_WEIGHT_CLIP = 1.0                   # weight = clip(|net_return|, 0, this)

# ── Selection guardrails (validation only; gate = beat the frozen baseline) ──
KEEP_THRESHOLDS = [0.50, 0.55, 0.60]       # P(win) needed to keep a proposal
MIN_KEPT_TRADES = 10
MAX_DRAWDOWN_CAP = 0.40
MIN_PASSING_SEEDS = 20        # of 40 seeds: require a majority to clear the gate

# ── Evaluation modes (v2.1) ───────────────────────────────────────────────────
# filter : keep every proposal at its strategy-frozen DTE with score >= thr
#          (v1 semantics), sequential compounding
# rank   : cross-sectional top-K portfolio — candidates at the same bar
#          compete on score (DTE variants of one trade dedupe to the
#          best-scored); up to MAX_CONCURRENT slots, PORTFOLIO_FRACTION of
#          equity each, P&L applied at each position's exit
EVAL_MODES = ["filter", "rank"]
MAX_CONCURRENT = 5
PORTFOLIO_FRACTION = 0.10
RANK_QUINTILES = 5                         # rank-calibration report buckets

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
