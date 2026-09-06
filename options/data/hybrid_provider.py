# options/data/hybrid_provider.py
"""Offline-first options data provider for label generation and research.

Serves the three :class:`OptionsDataProvider` calls from local data wherever
possible, falling back to a live provider (Massive) only for option bars that
have never been fetched — and persisting those so every later run is offline:

  get_chain           ← nn_options_signal universe.parquet (metadata only).
                        Point-in-time via ``as_of``: a contract "exists" iff
                        life_start <= as_of <= expiration. life_start is the
                        universe's bar-download window (expiration - 60d), so
                        contracts more than ~60 days from expiry are excluded
                        — conservative, and irrelevant for our <=45 DTE targets.
                        No greeks → the selector falls back to moneyness.
  get_contract_bars   ← parquet cache keyed by OCC symbol + interval
                        (``<cache_dir>/bars_15m/<OCC>.parquet``); cache misses
                        fetch the contract's FULL life from the live provider
                        (429 → sleep 15 s → retry) and persist, then slice the
                        requested window. Empty results are cached too, so a
                        contract that never printed is fetched exactly once.
  get_underlying_bars ← underlying_daily.parquet (1D) or the 15m parquet built
                        by ``python -m nn_meta.download_data``.

Frames use the project-standard schema (tz-naive UTC DatetimeIndex,
Open/High/Low/Close/Volume) so they drop straight into the simulator.
"""
from __future__ import annotations

import time
import tempfile
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from utils.logging_utils import setup_logging
from utils.error_handling import DataError
from options.data.provider import OptionsDataProvider, OptionContract, parse_occ_symbol

logger = setup_logging(log_file="logs/backtester.log")

_TAG = "OPT-HYBRID"
_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_UNIVERSE_PARQUET = _ROOT / "nn_options_signal" / "data_cache" / "universe.parquet"
DEFAULT_UNDERLYING_DAILY = _ROOT / "nn_options_signal" / "data_cache" / "underlying_daily.parquet"
DEFAULT_UNDERLYING_15M = _ROOT / "nn_meta" / "data_cache" / "underlying_15m.parquet"
DEFAULT_BARS_CACHE_DIR = _ROOT / "nn_meta" / "data_cache"

_OHLCV = ["Open", "High", "Low", "Close", "Volume"]

# Massive tiers (memory: options aggs ~120/s, sleep 15 s on 429)
_RETRY_SLEEP_S = 15
_MAX_RETRIES = 4

# Fallback life window when an OCC symbol is not in the universe parquet:
# matches the universe convention (DTE_MAX + 15 = 60) plus a small buffer.
_FALLBACK_LIFE_DAYS = 75


def _to_date(d) -> date:
    return d if isinstance(d, date) and not isinstance(d, pd.Timestamp) \
        else pd.Timestamp(d).date()


def _interval_key(interval: str) -> str:
    """Normalize an interval string to a cache-directory suffix."""
    return interval.lower().replace(" ", "")


def _contained_cache_path(root: Path, occ: str, interval: str) -> Path:
    key = _interval_key(interval)
    if (not occ or occ in (".", "..") or "/" in occ or "\\" in occ or "\0" in occ
            or not re.fullmatch(r"[a-z0-9]+", key)):
        raise DataError("Unsafe contract/interval cache key")
    path = root / f"bars_{key}" / f"{occ}.parquet"
    if not path.resolve().is_relative_to(root.resolve()):
        raise DataError("Contract cache path escapes its data root")
    return path


class HybridCachedProvider(OptionsDataProvider):
    """Local-parquet chains/underlying + cached on-demand option bars.

    ``bars_cache_dir`` is the sole writable materialization root. Optional
    ``bars_readonly_cache_dirs`` are searched in order after a writable-cache
    miss, before fetching; hits retain their values/attrs and are never copied
    or promoted into the writable cache. Empty hits retain the same semantics.
    """

    def __init__(
        self,
        universe_parquet: Path | str = DEFAULT_UNIVERSE_PARQUET,
        underlying_daily_parquet: Path | str = DEFAULT_UNDERLYING_DAILY,
        underlying_15m_parquet: Path | str = DEFAULT_UNDERLYING_15M,
        bars_cache_dir: Path | str = DEFAULT_BARS_CACHE_DIR,
        live_provider: Optional[OptionsDataProvider] = None,
        allow_fetch: bool = True,
        universe_df: Optional[pd.DataFrame] = None,
        bars_readonly_cache_dirs: tuple[Path | str, ...] = (),
    ):
        self._universe_path = Path(universe_parquet)
        self._und_daily_path = Path(underlying_daily_parquet)
        self._und_15m_path = Path(underlying_15m_parquet)
        self._cache_dir = Path(bars_cache_dir)
        self._readonly_cache_dirs = tuple(Path(p) for p in bars_readonly_cache_dirs)
        if any(self._cache_dir.resolve().is_relative_to(p.resolve()) for p in self._readonly_cache_dirs):
            raise DataError("Writable contract cache must be outside readonly data roots")
        self._live = live_provider          # constructed lazily if None
        self._allow_fetch = allow_fetch
        self._universe = universe_df        # injectable for tests
        # Per-underlying slices of the universe (2026-09-05, TODO block 6):
        # a symbol build only ever needs its OWN underlying (0.4% of the
        # 5.2M-row universe), so chains are served from a slice read with a
        # parquet predicate — ~MBs resident instead of ~1 GB, and get_chain
        # masks ~20k rows instead of 5.2M (310x measured). Row order within
        # an underlying is the file's order, exactly as before.
        self._slices: dict[str, pd.DataFrame] = {}
        self._life_indexes: dict[str, dict[str, tuple[date, date]]] = {}
        self._life_fallbacks: dict[str, tuple[date, date]] = {}
        self._und_daily: Optional[pd.DataFrame] = None
        self._und_15m: Optional[pd.DataFrame] = None
        self.fetch_count = 0                # live fetches this session (stats)
        self.cache_counts = {"writable_hit": 0, "readonly_hit": 0, "materialized": 0}

    # ── lazy loads ───────────────────────────────────────────────────────────
    def _get_universe(self) -> pd.DataFrame:
        if self._universe is None:
            if not self._universe_path.exists():
                raise DataError(f"Universe parquet not found: {self._universe_path}")
            self._universe = pd.read_parquet(self._universe_path)
            logger.info(f"[{_TAG}] universe loaded: {len(self._universe):,} contracts")
        if not self._universe.attrs.get("hybrid_normalized"):
            # Universe tickers carry the vendor "O:" prefix; OptionContract.symbol
            # is the bare OCC symbol everywhere else in the options subsystem.
            self._universe = self._normalize(self._universe)
        return self._universe

    @staticmethod
    def _normalize(u: pd.DataFrame) -> pd.DataFrame:
        u = u.copy()
        u["expiration"] = pd.to_datetime(u["expiration"])
        u["life_start"] = pd.to_datetime(u["life_start"])
        u["ticker"] = u["ticker"].str.removeprefix("O:")
        u.attrs["hybrid_normalized"] = True
        return u

    def _get_slice(self, underlying: str) -> pd.DataFrame:
        """The universe rows for one underlying, normalized, in file order.
        Served from the in-memory frame when one was injected/loaded, else
        read straight from the parquet with a predicate (row groups that
        cannot contain the underlying are skipped when the file is sorted)."""
        und = underlying.upper()
        sl = self._slices.get(und)
        if sl is None:
            if self._universe is not None:
                u = self._get_universe()
                sl = u[u["underlying"] == und].reset_index(drop=True)
            else:
                if not self._universe_path.exists():
                    raise DataError(f"Universe parquet not found: {self._universe_path}")
                raw = pd.read_parquet(self._universe_path,
                                      filters=[("underlying", "==", und)])
                sl = self._normalize(raw).reset_index(drop=True)
                logger.info(f"[{_TAG}] universe slice {und}: {len(sl):,} contracts")
            self._slices[und] = sl
        return sl

    def _get_live(self) -> OptionsDataProvider:
        if self._live is None:
            from options.data.massive_provider import MassiveProvider
            self._live = MassiveProvider()
        return self._live

    # ── chains ───────────────────────────────────────────────────────────────
    # This capability means as_of filters the observed catalogue by life_start.
    # It does not assert an intraday listing clock; expanded research lags a date.
    point_in_time_chain = True

    def historical_chain_member(self, underlying, occ, as_of):
        """Bind renamed OCC roots to explicit prior-date universe metadata."""
        u = self._get_slice(underlying)
        stamp = pd.Timestamp(_to_date(as_of))
        return bool(((u["ticker"] == occ) & (u["life_start"] <= stamp)
                     & (u["expiration"] >= stamp)).any())

    def get_chain(self, underlying, *, right=None, expiration_gte=None,
                  expiration_lte=None, strike_gte=None, strike_lte=None,
                  as_of=None) -> list[OptionContract]:
        u = self._get_slice(underlying)
        m = pd.Series(True, index=u.index)
        if right:
            m &= u["type"] == ("call" if right.upper().startswith("C") else "put")
        if expiration_gte is not None:
            m &= u["expiration"] >= pd.Timestamp(_to_date(expiration_gte))
        if expiration_lte is not None:
            m &= u["expiration"] <= pd.Timestamp(_to_date(expiration_lte))
        if strike_gte is not None:
            m &= u["strike"] >= strike_gte
        if strike_lte is not None:
            m &= u["strike"] <= strike_lte
        if as_of is not None:
            ts = pd.Timestamp(_to_date(as_of))
            m &= (u["life_start"] <= ts) & (u["expiration"] >= ts)

        sel = u[m]
        return [
            OptionContract(
                symbol=r.ticker, underlying=r.underlying,
                expiration=r.expiration.date(), strike=float(r.strike),
                right="C" if r.type == "call" else "P",
            )
            for r in sel.itertuples()
        ]

    # ── option bars: cache-first, fetch-on-miss ──────────────────────────────
    def _cache_path(self, occ: str, interval: str) -> Path:
        return _contained_cache_path(self._cache_dir, occ, interval)

    def _life_window(self, occ: str) -> tuple[date, date]:
        """Exact universe life using one cached ticker index per underlying.

        Reuses chain slices instead of loading/masking the entire universe on
        every materialization. First duplicate within a slice wins, as before.
        Old OCC roots catalogued under a renamed underlying use a ticker
        predicate fallback, preserving metadata life before the 75-day default.
        """
        if occ in self._life_fallbacks:
            return self._life_fallbacks[occ]
        root, exp, _, _ = parse_occ_symbol(occ)
        if root not in self._life_indexes:
            index = {}
            for row in self._get_slice(root).itertuples():
                index.setdefault(row.ticker, (row.life_start.date(), row.expiration.date()))
            self._life_indexes[root] = index
        window = self._life_indexes[root].get(occ)
        if window is not None:
            return window
        if self._universe is not None:
            universe = self._get_universe()
            rows = universe[universe["ticker"] == occ]
        else:
            rows = self._normalize(pd.read_parquet(
                self._universe_path, filters=[("ticker", "in", [occ, "O:" + occ])]))
        if rows.empty:
            window = (exp - timedelta(days=_FALLBACK_LIFE_DAYS), exp)
        else:
            row = rows.iloc[0]
            window = (row.life_start.date(), row.expiration.date())
        self._life_fallbacks[occ] = window
        return window

    def _assert_writable_cache_path(self, path: Path) -> None:
        resolved = path.resolve()
        if (not resolved.is_relative_to(self._cache_dir.resolve()) or
                any(resolved.is_relative_to(p.resolve()) for p in self._readonly_cache_dirs)):
            raise DataError("Contract materialization path escapes writable cache or enters readonly data")

    def _fetch_with_retry(self, occ: str, frm: date, to: date,
                          interval: str) -> "pd.DataFrame | None":
        """Fetch with backoff on transient failures. Returns None (not raise)
        when a TRANSIENT error persists past the retry budget, so a single flaky
        contract degrades to 'no data this pass' instead of killing a multi-hour
        build. Non-transient errors (auth, bad request) still raise."""
        for attempt in range(_MAX_RETRIES + 1):
            try:
                self.fetch_count += 1
                return self._get_live().get_contract_bars(
                    occ, frm.isoformat(), to.isoformat(), interval)
            except DataError as e:
                msg = str(e)
                is_429 = "429" in msg
                # network blips surface as "request failed" (timeout / conn reset)
                transient = is_429 or "request failed" in msg \
                    or "timed out" in msg or "Connection" in msg
                if not transient:
                    raise                       # real error (e.g. 403) — surface it
                if attempt >= _MAX_RETRIES:
                    logger.warning(f"[{_TAG}] {occ}: transient fetch failure past "
                                   f"{_MAX_RETRIES} retries, skipping (uncached): "
                                   f"{msg[:100]}")
                    return None
                sleep_s = _RETRY_SLEEP_S if is_429 else min(2 ** attempt, 20)
                logger.warning(f"[{_TAG}] {occ}: {'429' if is_429 else 'network'} "
                               f"error, sleeping {sleep_s}s "
                               f"(attempt {attempt + 1}/{_MAX_RETRIES})")
                time.sleep(sleep_s)
        return None  # pragma: no cover

    def get_contract_bars(self, occ_symbol, start, end, interval) -> pd.DataFrame:
        occ = occ_symbol[2:] if occ_symbol.startswith("O:") else occ_symbol
        path = self._cache_path(occ, interval)

        if path.exists():
            df = pd.read_parquet(path)
            self.cache_counts["writable_hit"] += 1
        else:
            fallback = next((p for root in self._readonly_cache_dirs
                             if (p := _contained_cache_path(root, occ, interval)).exists()), None)
            if fallback is not None:
                df = pd.read_parquet(fallback)
                self.cache_counts["readonly_hit"] += 1
            else:
                df = None
        if df is None and self._allow_fetch:
            frm, exp = self._life_window(occ)
            to = min(exp + timedelta(days=1), date.today())
            df = self._fetch_with_retry(occ, frm, to, interval)
            if df is None:
                # transient failure — return empty WITHOUT caching so the next
                # run retries this contract rather than caching a false blank.
                return pd.DataFrame(columns=_OHLCV)
            self._assert_writable_cache_path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._assert_writable_cache_path(path)
            # Separate workers may miss the same contract. Unique temporary
            # files prevent one worker replacing another worker's open file.
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".contract-", suffix=".tmp", delete=False) as stream:
                tmp = Path(stream.name)
            try:
                df.to_parquet(tmp)  # genuine empty results still cached once
                tmp.replace(path)
            finally:
                tmp.unlink(missing_ok=True)
            self.cache_counts["materialized"] += 1
        elif df is None:
            logger.info(f"[{_TAG}] {occ} {interval}: not cached and fetch disabled")
            return pd.DataFrame(columns=_OHLCV)

        if df.empty:
            return df
        lo = pd.Timestamp(_to_date(start))
        hi = pd.Timestamp(_to_date(end)) + pd.Timedelta(days=1)
        return df[(df.index >= lo) & (df.index < hi)]

    # ── underlying bars ──────────────────────────────────────────────────────
    def _underlying_frame(self, path: Path, cache_attr: str) -> pd.DataFrame:
        cached = getattr(self, cache_attr)
        if cached is None:
            if not path.exists():
                raise DataError(
                    f"Underlying bars parquet not found: {path}. "
                    f"Run `python -m nn_meta.download_data` first.")
            cached = pd.read_parquet(path)
            setattr(self, cache_attr, cached)
        return cached

    def get_underlying_bars(self, symbol, start, end, interval) -> pd.DataFrame:
        key = _interval_key(interval)
        if key in ("1d",):
            df = self._underlying_frame(self._und_daily_path, "_und_daily")
            sym_col = "underlying" if "underlying" in df.columns else None
            sub = df[df[sym_col] == symbol.upper()] if sym_col else df
            sub = sub[(sub["date"] >= pd.Timestamp(_to_date(start)))
                      & (sub["date"] <= pd.Timestamp(_to_date(end)))]
            out = sub.rename(columns={"open": "Open", "high": "High", "low": "Low",
                                      "close": "Close", "volume": "Volume"})
            out = out.set_index(pd.to_datetime(sub["date"]))
            out.index.name = "timestamp"
            return out[_OHLCV]
        if key == "15m":
            df = self._underlying_frame(self._und_15m_path, "_und_15m")
            sub = df[df["symbol"] == symbol.upper()]
            lo = pd.Timestamp(_to_date(start))
            hi = pd.Timestamp(_to_date(end)) + pd.Timedelta(days=1)
            sub = sub[(sub["timestamp"] >= lo) & (sub["timestamp"] < hi)]
            out = sub.set_index("timestamp")[_OHLCV]
            out.index.name = "timestamp"
            return out
        raise DataError(f"[{_TAG}] Unsupported underlying interval '{interval}' "
                        f"(supported: 15m, 1d/1D)")
