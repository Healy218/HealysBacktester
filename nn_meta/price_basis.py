"""Raw contemporaneous stock prices for comparisons with listed OCC strikes.

Adjusted bars remain the technical/return history. The separate raw panel is
mandatory for historical option selection and implied volatility: changing a
filename or copying adjusted prices cannot establish the required lineage.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

RAW_SPOT_SCHEMA_VERSION = "2026-09-06-raw-spot-v1"
RAW_SPOT_BASIS = "raw"


class PriceBasisError(ValueError):
    """Missing or incompatible underlying price basis."""


def raw_spot_provenance(interval: str, *, provider: str, feed: str) -> dict:
    """Metadata writers attach only after an explicit unadjusted vendor fetch."""
    if interval not in ("1d", "15m") or not provider or not feed:
        raise PriceBasisError("raw spot needs interval1d/15m and explicit provider/feed")
    return {"schema_version": RAW_SPOT_SCHEMA_VERSION, "price_basis": RAW_SPOT_BASIS,
            "adjustment": "raw", "provider": provider, "feed": feed, "interval": interval}


def require_raw_panel(panel: pd.DataFrame, interval: str) -> pd.DataFrame:
    """Validate declared provenance, exact keys and positive raw Close prices."""
    if not isinstance(panel, pd.DataFrame):
        raise PriceBasisError("raw underlying panel is required; adjusted-price fallback is forbidden")
    expected = {"schema_version": RAW_SPOT_SCHEMA_VERSION, "price_basis": RAW_SPOT_BASIS,
                "adjustment": "raw", "interval": interval}
    for key, value in expected.items():
        if panel.attrs.get(key) != value:
            raise PriceBasisError(f"raw underlying {key} must be {value!r}; rebuild the separate raw spot cache")
    if any(not isinstance(panel.attrs.get(key), str) or not panel.attrs[key].strip() for key in ("provider", "feed")):
        raise PriceBasisError("raw underlying cache requires explicit provider/feed provenance")
    if interval == "1d":
        symbol, stamp, price = "underlying", "date", "close"
    elif interval == "15m":
        symbol, stamp, price = "symbol", "timestamp", "Close"
    else:
        raise PriceBasisError("raw underlying interval must be 1d or15m")
    if any(key not in panel for key in (symbol, stamp, price)):
        raise PriceBasisError(f"raw underlying cache requires {symbol}, {stamp}, {price}")
    if panel.empty:
        raise PriceBasisError("raw underlying cache is empty")
    if (panel[symbol].isna().any() or not panel[symbol].map(lambda s: isinstance(s, str) and bool(s.strip())).all()):
        raise PriceBasisError("raw underlying symbols must be nonempty strings")
    if not pd.api.types.is_datetime64_dtype(panel[stamp]):
        raise PriceBasisError(f"raw {stamp} must use tz-naive UTC datetime64 values")
    if panel[stamp].isna().any() or panel.duplicated([symbol, stamp]).any():
        raise PriceBasisError("raw underlying keys must be complete and unique")
    if interval == "1d" and (panel[stamp] != panel[stamp].dt.normalize()).any():
        raise PriceBasisError("raw daily dates must be normalized session dates")
    values = panel[price]
    if (not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values)
            or not np.isfinite(values.to_numpy(float)).all() or (values <= 0).any()):
        raise PriceBasisError("raw underlying Close must be finite and strictly positive")
    return panel


def raw_daily_path() -> Path:
    from nn_meta import config
    return Path(getattr(config, "UNDERLYING_DAILY_RAW_PARQUET", config.DATA_CACHE / "underlying_daily_raw.parquet"))


def raw_15m_path() -> Path:
    from nn_meta import config
    return Path(getattr(config, "UNDERLYING_15M_RAW_PARQUET", config.DATA_CACHE / "underlying_15m_raw.parquet"))


def load_raw_daily() -> pd.DataFrame:
    path = raw_daily_path()
    if not path.is_file():
        raise FileNotFoundError(f"{path} missing; fetch separate raw daily spot before surface/universe build")
    panel = require_raw_panel(pd.read_parquet(path), "1d")
    panel.attrs["source_path"] = str(path)
    return panel


def raw_daily_for_roots(panel: pd.DataFrame, aliases: dict[str, str] | None = None) -> pd.DataFrame:
    """Explicit renamed-root mapping; exact raw root/date observations win.

    This only copies already observed raw prices from a declared equivalent
    ticker. It never forward/back-fills unavailable historical sessions.
    The original panel is unchanged and every used mapping is recorded.
    """
    require_raw_panel(panel, "1d")
    aliases = dict(aliases or {})
    if any(not isinstance(old, str) or not isinstance(new, str) or not old or not new or old == new
           for old, new in aliases.items()):
        raise PriceBasisError("raw root aliases must map distinct nonempty symbol strings")
    frames, used = [panel], {}
    existing = pd.MultiIndex.from_frame(panel[["underlying", "date"]])
    for old, new in aliases.items():
        candidates = panel.loc[panel.underlying == new].copy()
        candidates["underlying"] = old
        candidates = candidates[~pd.MultiIndex.from_frame(candidates[["underlying", "date"]]).isin(existing)]
        if not candidates.empty:
            frames.append(candidates)
            used[old] = {"raw_symbol": new, "sessions_added": len(candidates),
                         "first_session": candidates.date.min().isoformat(),
                         "last_session": candidates.date.max().isoformat()}
    result = pd.concat(frames, ignore_index=True)
    result.attrs = dict(panel.attrs, explicit_root_aliases=aliases, resolved_root_aliases=used)
    return require_raw_panel(result, "1d")


def require_raw_surface(surface: pd.DataFrame) -> None:
    """Old adjusted-spot IV panels are ineligible even when columns match."""
    if (surface.attrs.get("surface_schema_version") != RAW_SPOT_SCHEMA_VERSION
            or surface.attrs.get("option_strike_spot_basis") != RAW_SPOT_BASIS):
        raise PriceBasisError("option surface lacks current raw-spot provenance; rebuild surface_daily before feature assembly")


def require_raw_universe(universe: pd.DataFrame) -> None:
    """Accept audited raw-filtered or complete unfiltered observed contracts."""
    current = universe.attrs.get("universe_price_basis_schema") == RAW_SPOT_SCHEMA_VERSION
    raw_filtered = universe.attrs.get("strike_filter_spot_basis") == RAW_SPOT_BASIS
    complete = (universe.attrs.get("contract_scope") == "all_observed_contracts"
                and universe.attrs.get("source") == "flatfiles_15m"
                and universe.attrs.get("strike_filter") == "none"
                and bool(universe.attrs.get("derivation_provenance")))
    if not current or not (raw_filtered or complete):
        raise PriceBasisError("option universe lacks raw-spot strike-filter provenance; rebuild universe and audit newly admitted contract-bar coverage")


def require_raw_daily_options(panel: pd.DataFrame) -> None:
    """Surface bars must not retain a previous adjusted-spot ATM prefilter."""
    if (panel.attrs.get("daily_price_basis_schema") != RAW_SPOT_SCHEMA_VERSION
            or panel.attrs.get("moneyness_filter_spot_basis") not in ("raw", "unfiltered")):
        raise PriceBasisError("daily option part lacks raw-filter provenance; rederive bars_daily before surface assembly")


@lru_cache(maxsize=32)
def _raw_symbol(path: str, symbol: str, size: int, modified_ns: int) -> pd.Series:
    # Arrow filters avoid reading every symbol for each strategy/DTE. Stat
    # fields invalidate the cache after an atomic download replacement.
    panel = require_raw_panel(pd.read_parquet(path, filters=[("symbol", "==", symbol)]), "15m")
    close = panel.set_index("timestamp")["Close"].sort_index()
    close.attrs = dict(panel.attrs, symbol=symbol, source_path=path, source_size=size, source_mtime_ns=modified_ns)
    return close


def load_raw_close_15m(symbol: str, *, index: pd.DatetimeIndex | None = None) -> pd.Series:
    path = raw_15m_path()
    if not path.is_file():
        raise FileNotFoundError(f"{path} missing; option selection requires a separate raw15m spot cache")
    stat = path.stat()
    close = _raw_symbol(str(path), symbol.upper(), stat.st_size, stat.st_mtime_ns).copy()
    if index is not None:
        expected = pd.DatetimeIndex(index)
        if expected.tz is not None:
            expected = expected.tz_convert("UTC").tz_localize(None)
        if not expected.is_unique or not expected.is_monotonic_increasing or expected.hasnans:
            raise PriceBasisError("selection timeline must have unique increasing timestamps")
        missing = expected.difference(close.index)
        if len(missing):
            raise PriceBasisError(f"raw15m spot missing {len(missing)} required {symbol} timestamps; first={missing[0]}; no adjusted fallback")
        close = close.reindex(expected)
    return close


def require_raw_close(close: pd.Series) -> None:
    """Execution guard before converting price values to untyped floats."""
    if (not isinstance(close, pd.Series) or close.attrs.get("price_basis") != RAW_SPOT_BASIS
            or close.attrs.get("adjustment") != "raw"
            or close.attrs.get("schema_version") != RAW_SPOT_SCHEMA_VERSION
            or close.attrs.get("interval") != "15m"):
        raise PriceBasisError("option execution requires explicitly sourced raw15m spot prices")
    if (not isinstance(close.index, pd.DatetimeIndex) or close.index.tz is not None
            or not close.index.is_unique or not close.index.is_monotonic_increasing
            or close.index.hasnans):
        raise PriceBasisError("raw selection spot index must be unique increasing tz-naive UTC")
    if (not pd.api.types.is_numeric_dtype(close) or pd.api.types.is_bool_dtype(close)
            or not np.isfinite(close.to_numpy(float)).all() or (close <= 0).any()):
        raise PriceBasisError("raw selection spot must be finite and positive")
    if not close.attrs.get("provider") or not close.attrs.get("feed"):
        raise PriceBasisError("raw selection spot requires provider/feed provenance")
    if not isinstance(close.attrs.get("symbol"), str) or not close.attrs["symbol"].strip():
        raise PriceBasisError("raw selection spot requires explicit symbol identity")
