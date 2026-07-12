# nn_meta/providers.py
"""Binds the option-bar provider to nn_meta's own data cache. Big-run pools
(v3.1+) use FlatFilesProvider — option bars come from the prebuilt flat-file
day-frames instead of the REST API; everything else is inherited."""
from options.data.hybrid_provider import HybridCachedProvider

from nn_meta import config


def get_provider(**kwargs):
    common = dict(
        universe_parquet=config.UNIVERSE_PARQUET,
        underlying_daily_parquet=config.UNDERLYING_DAILY_PARQUET,
        underlying_15m_parquet=config.UNDERLYING_15M_PARQUET,
        bars_cache_dir=config.DATA_CACHE,
        **kwargs,
    )
    if config._BIG_RUN:
        from v3.flatfiles import FlatFilesProvider
        return FlatFilesProvider(
            flatfiles_dir=config.DATA_CACHE / "flatfiles_15m", **common)
    return HybridCachedProvider(**common)
