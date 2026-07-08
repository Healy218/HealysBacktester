# v3/underlying.py — Stage 2: 1m crawl → resample stack → partitioned parquet.
"""Download config.BASE_INTERVAL only; derive config.RESAMPLE_STACK by
resampling (one quota spend, zero cross-feed misalignment). Partition
underlying/<symbol>/<year>.parquet, checksummed. Done once, then boring."""


def crawl_symbol(symbol: str) -> None:
    """Fetch full-window 1m bars for `symbol` into UNDERLYING_DIR."""
    raise NotImplementedError("Stage 2 — see V3_SPEC.md")


def resample(symbol: str, interval: str):
    """Derive `interval` bars from the stored 1m partition."""
    raise NotImplementedError("Stage 2 — see V3_SPEC.md")
