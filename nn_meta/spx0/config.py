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
# Round 3: intraday-native strategies (SPX0_SPEC item 3). Each param setting
# is its own strategy seat — the fold's model/policy selection chooses among
# them, which is what "params swept in-fold" means in this machinery.
INTRADAY_STRATEGIES = ["vwap_rev_15", "vwap_rev_20", "orb_15", "orb_30",
                       "gap_fill_30", "gap_fill_50"]
STRATEGIES += INTRADAY_STRATEGIES
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


@dataclass(frozen=True)
class TradeVariant:
    """One fold-selectable execution variant of a signal (SPX0_SPEC "Second
    design round"). ``code`` rides the dataset's ``dte`` column — slot 4 of the
    stable trade_id — so rank/EV dedupe on (symbol, strategy, trade_idx) makes
    the variant fold-selectable exactly like DTE is in v4: 0 is the round-1
    long default (the frozen baseline), positive codes are long stops ×100,
    negative codes are sell-premium stops ×(−100).

    A short variant SELLS the opposite right (bullish signal sells the PUT) and
    posts ``margin = (stop_frac − 1) × entry premium`` — the max planned loss,
    enforced by the premium stop at ``stop_frac × entry``. Returns are per unit
    margin, so they live in the ledger's per-position units and −1 means the
    stop fired at its level (gaps/settlement past the stop can exceed it;
    that's data, not a bug).

    ``wing_strikes > 0`` (round 3, after the round-2 naked-short test blowup)
    makes a short a CREDIT VERTICAL: the sold leg plus a bought wing that many
    strike-steps further OTM. Margin = width − credit — the true worst case by
    CONSTRUCTION (settlement cannot exceed the width), so no premium stop is
    needed or used; the loss floor is −1 − exit-slippage/margin, not a gap."""
    code: int
    short: bool
    stop_frac: float
    target_mult: float = float("inf")
    wing_strikes: int = 0


ROUND2_VARIANTS = (
    TradeVariant(0, False, 0.50),          # round-1 default; the frozen baseline
    TradeVariant(30, False, 0.30),
    TradeVariant(70, False, 0.70),
    TradeVariant(-150, True, 1.50),
    TradeVariant(-200, True, 2.00),
    TradeVariant(-300, True, 3.00),
)

# Round 3 (EXPERIMENTS 2026-08-24): naked shorts are out — their tail cannot
# be bounded by a stop. Credit verticals replace them (loss bounded by
# construction); the long stop grid stays. Codes -(1000 + wing_strikes).
ROUND3_VARIANTS = (
    TradeVariant(0, False, 0.50),
    TradeVariant(30, False, 0.30),
    TradeVariant(70, False, 0.70),
    TradeVariant(-1001, True, float("inf"), wing_strikes=1),
    TradeVariant(-1002, True, float("inf"), wing_strikes=2),
    TradeVariant(-1004, True, float("inf"), wing_strikes=4),
)

# P(win) grid for this pool. The shared KEEP_THRESHOLDS (>= 0.50) assume the
# equity pool's base rate; a long-0DTE book wins ~27% of the time (80-session
# build, 2026-08-21), so a 0.5 cut keeps nothing. These sit around that base
# rate; the EV mode (sign of predicted return) is base-rate free. The upper
# rungs exist for the round-2 sell-premium variants, whose base rate is the
# long book's complement (~0.7+).
KEEP_THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65]

SPX0_FEATURES = [
    "spx0_rv_30", "spx0_rv_60", "spx0_min_since_open", "spx0_min_to_expiry",
    "spx0_depth_signal", "spx0_prem_spot_last", "spx0_ratio",
    # round 2: the variant axis (the model must see what it is ranking) and
    # premium richness — last premium/spot vs the realized-vol move to expiry.
    "spx0_short", "spx0_stop_frac", "spx0_prem_rich",
    # round 3: vertical width as a fraction of spot (0 = not a vertical)
    "spx0_wing_width_frac",
]
