# nn_meta/providers.py
"""Binds the option-bar provider to nn_meta's own data cache. Big-run pools
(v3.1+) use FlatFilesProvider — option bars come from the prebuilt flat-file
day-frames instead of the REST API. Named historical campaigns materialize
contract slices under RUNS_DIR/provider_cache; DATA_CACHE is a readonly fallback.
Live and unnamed provider cache locations keep their existing behavior."""
from options.data.hybrid_provider import HybridCachedProvider
import pandas as pd
from pathlib import Path

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
    )
    common.update(kwargs)
    if config.CAMPAIGN and not live:
        # Sealed candidate/source data is immutable. Materialized per-contract
        # slices are disposable outputs belonging to this named campaign.
        writable = config.RUNS_DIR / "provider_cache"
        selected = Path(kwargs.get("bars_cache_dir", writable))
        if not selected.resolve().is_relative_to(writable.resolve()):
            raise ValueError("Named research contract cache must stay under RUNS_DIR/provider_cache")
        readonly = tuple(dict.fromkeys((config.DATA_CACHE,
                                       *kwargs.get("bars_readonly_cache_dirs", ()))))
        common.update(bars_cache_dir=selected, bars_readonly_cache_dirs=readonly)
    if config._BIG_RUN and not live:
        from v3.flatfiles import FlatFilesProvider
        return FlatFilesProvider(
            flatfiles_dir=config.DATA_CACHE / "flatfiles_15m", **common)
    return HybridCachedProvider(**common)
