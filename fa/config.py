# fa/config.py — shared constants for the discovery pipeline (FA_SPEC.md).
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "archive"           # append-only: <source>/<yyyy-mm>.parquet
ARTIFACTS = ROOT / "artifacts"       # frozen rankings, tracker state

SUBREDDITS = ["wallstreetbets", "stocks", "options", "investing"]

# Scoring
BASELINE_DAYS = 90                   # velocity z-score vs own trailing baseline
CORROBORATION_MIN = 2                # independent source families for top-10 entry

# Ranking
TOP_N = 10
CADENCE = "monthly"                  # open question in spec: monthly vs weekly

# Graduation (into the training universe, point-in-time as of ranking date)
PROBATION_MONTHS = 3                 # open question in spec: 3 vs 6

# Liquidity floor — trending-but-untradeable is trivia, not a candidate
MIN_ADV_USD = 5_000_000
MIN_OPTION_OI = 1_000
