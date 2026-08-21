"""spx0 pool constants — kept out of nn_meta/config.py so the v31 paths stay
untouched. Design: docs/specs/SPX0_SPEC.md."""
from __future__ import annotations

from dataclasses import dataclass

from nn_meta import config as _c

DATA_CACHE = _c.ROOT / "data_cache_spx0"
FLATFILES_1M = DATA_CACHE / "flatfiles_1m"
UNDERLYING_1M = DATA_CACHE / "underlying_1m"
ARTIFACTS = _c.ROOT / "artifacts_spx0"
ROWS_DIR = ARTIFACTS / "rows"
MARKS_DIR = ARTIFACTS / "marks"
DATASET = ARTIFACTS / "meta_dataset.parquet"

WINDOW_START, WINDOW_END = "2024-08-16", "2026-08-14"
INDEXES = ("SPX", "NDX")
PROXY = {"SPX": "SPY", "NDX": "QQQ"}
STRATEGIES = list(_c.PROPOSAL_STRATEGIES_V31)      # ma, macd, rsi, squeeze, tv_rating
SIGNAL_BAR = "5min"                                # proxy bars the strategies see
MAX_DRAWDOWN_CAP = 0.25                            # tighter than the shared 0.40
LAST_ENTRY_MINUTES_BEFORE_CLOSE = 30               # no fresh 0DTE entries in the last half hour


@dataclass(frozen=True)
class ExitPolicy:
    """Signal-driven exit plus hard stop/target on the option premium and the
    session floor. A fixed variant per build; alternatives are selected
    inside temporal folds, never on test."""
    name: str = "s50_nocap"
    stop_frac: float = 0.50        # exit if premium <= 50% of entry
    target_mult: float = float("inf")   # NO upside cap (ROADMAP: "no upside cap");
                                        # a finite value is a fold-selectable variant


DEFAULT_EXIT = ExitPolicy()

# P(win) grid for this pool. The shared KEEP_THRESHOLDS (>= 0.50) assume the
# equity pool's base rate; a long-0DTE book wins ~27% of the time (80-session
# build, 2026-08-21), so a 0.5 cut keeps nothing. These sit around that base
# rate; the EV mode (sign of predicted return) is base-rate free.
KEEP_THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50]

SPX0_FEATURES = [
    "spx0_rv_30", "spx0_rv_60", "spx0_min_since_open", "spx0_min_to_expiry",
    "spx0_depth_signal", "spx0_prem_spot_last", "spx0_ratio",
]
