# v3/config.py — shared constants for the v3 pipeline (V3_SPEC.md).
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Window (Stage 0 audit may push WINDOW_START later — decided there, not here)
WINDOW_START = "2017-01-20"          # Trump 1st inauguration
WINDOW_END = None                    # None → present at build time

# Universe
UNIVERSE_TARGET = 200                # minimum names after liquidity gates
RECONSTITUTION = "annual"            # open question in spec: annual vs quarterly

# Data layout — parquet, partitioned; hard rule: no 100k-tiny-file directories
DATA_DIR = ROOT / "data"             # underlying/<symbol>/<year>.parquet
UNDERLYING_DIR = DATA_DIR / "underlying"
OPTION_CACHE_DIR = DATA_DIR / "option_bars"   # <symbol>/<yyyy-mm>.parquet
ARTIFACTS = ROOT / "artifacts"

BASE_INTERVAL = "1min"               # the only downloaded interval
RESAMPLE_STACK = ["5min", "15min", "1h", "1d"]  # derived, never downloaded
