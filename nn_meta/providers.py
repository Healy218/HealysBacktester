# nn_meta/providers.py
"""Binds the option-bar provider to nn_meta's own data cache. Big-run pools
(v3.1+) use FlatFilesProvider — option bars come from the prebuilt flat-file
day-frames instead of the REST API; everything else is inherited."""
from options.data.hybrid_provider import HybridCachedProvider
import pandas as pd

from nn_meta import config


def get_provider(live: bool = False, **kwargs):
    """``live=True`` forces the REST-backed hybrid provider even for big-run
    pools: flat files are a *history* archive (nothing for today, and absent
    on deployed hosts), so live scoring under NN_META_POOL=v31 must price
    contracts through the same on-demand path v2/v3 use. For v2/v3 the flag
    is a no-op (hybrid either way)."""
    if not live:
        from nn_meta.price_basis import require_raw_universe
        # Read metadata without materializing the multi-million-row chain.
        universe = kwargs.get("universe_df")
        if universe is None:
            universe = pd.read_parquet(kwargs.get("universe_parquet", config.UNIVERSE_PARQUET), columns=[])
        require_raw_universe(universe)
    common = dict(
        universe_parquet=config.UNIVERSE_PARQUET,
        underlying_daily_parquet=config.UNDERLYING_DAILY_PARQUET,
        underlying_15m_parquet=config.UNDERLYING_15M_PARQUET,
        bars_cache_dir=config.DATA_CACHE,
        **kwargs,
    )
    if config._BIG_RUN and not live:
        from v3.flatfiles import FlatFilesProvider
        return FlatFilesProvider(
            flatfiles_dir=config.DATA_CACHE / "flatfiles_15m", **common)
    return HybridCachedProvider(**common)
