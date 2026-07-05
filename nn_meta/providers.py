# nn_meta/providers.py
"""Single place that binds HybridCachedProvider to nn_meta's own data cache
(v2 universe/underlying parquets) instead of the provider's nn_options_signal
defaults."""
from options.data.hybrid_provider import HybridCachedProvider

from nn_meta import config


def get_provider(**kwargs) -> HybridCachedProvider:
    return HybridCachedProvider(
        universe_parquet=config.UNIVERSE_PARQUET,
        underlying_daily_parquet=config.UNDERLYING_DAILY_PARQUET,
        underlying_15m_parquet=config.UNDERLYING_15M_PARQUET,
        bars_cache_dir=config.DATA_CACHE,
        **kwargs,
    )
