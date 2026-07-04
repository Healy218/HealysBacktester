# options/data/massive_provider.py
"""
Massive (formerly Polygon.io) implementation of :class:`OptionsDataProvider`.

Uses the Polygon-compatible REST API at ``https://api.massive.com``. Unlike the
Alpaca free feed, Massive returns deep HISTORICAL option bars — including for
long-expired contracts — so this is the provider that actually powers backtests.

Endpoints
---------
    underlying bars   GET /v2/aggs/ticker/{ticker}/range/{mult}/{span}/{from}/{to}
    option bars       GET /v2/aggs/ticker/O:{occ}/range/{mult}/{span}/{from}/{to}
    contract listing  GET /v3/reference/options/contracts   (supports as_of + expired)

Notes
-----
* Auth: ``apiKey`` query parameter, read from ``MASSIVE_API_KEY``.
* The historical chain is point-in-time via ``as_of``; the contracts-reference
  endpoint carries **no greeks**, so selection uses moneyness (spot-relative),
  which the selector already supports. (Greeks are only on the live snapshot.)
* Verified 2026-07-02: base host ``api.massive.com``, expired-contract bars, and
  ``as_of`` point-in-time queries all return data on the "Options Starter" plan.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Optional

import pandas as pd
import requests

from utils.logging_utils import setup_logging
from utils.error_handling import DataError
from options.data.provider import OptionsDataProvider, OptionContract, parse_occ_symbol

logger = setup_logging(log_file="logs/backtester.log")

_DEFAULT_BASE = os.environ.get("MASSIVE_BASE_URL", "https://api.massive.com")

# interval string → (multiplier, timespan) for the aggregates endpoint
_TIMESPAN = {
    "1m": (1, "minute"), "5m": (5, "minute"), "15m": (15, "minute"),
    "30m": (30, "minute"), "1h": (1, "hour"), "60m": (1, "hour"),
    "1d": (1, "day"), "1D": (1, "day"),
}


def _as_date(d) -> date:
    return d if isinstance(d, date) else datetime.fromisoformat(str(d)).date()


def _d(d) -> str:
    return _as_date(d).isoformat()


class MassiveProvider(OptionsDataProvider):
    """Historical options + underlying data via the Massive/Polygon REST API."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = _DEFAULT_BASE):
        self._key = api_key or os.environ.get("MASSIVE_API_KEY", "")
        if not self._key:
            raise DataError("MASSIVE_API_KEY not found. Set it in your .env file.")
        self._base = base_url.rstrip("/")
        self._session = requests.Session()

    # ── low-level GET with auth + error handling ─────────────────────────────
    def _get(self, path: str, params: dict) -> dict:
        params = {k: v for k, v in params.items() if v is not None}
        params["apiKey"] = self._key
        try:
            r = self._session.get(self._base + path, params=params, timeout=30)
        except requests.RequestException as e:
            raise DataError(f"Massive request failed ({path}): {e}") from e
        if r.status_code != 200:
            raise DataError(f"Massive HTTP {r.status_code} for {path}: {r.text[:200]}")
        body = r.json()
        if body.get("status") not in ("OK", "DELAYED", None):
            raise DataError(f"Massive status {body.get('status')} for {path}: {body.get('error', '')}")
        return body

    def _timespan(self, interval: str):
        ts = _TIMESPAN.get(interval)
        if ts is None:
            raise DataError(
                f"Unsupported interval '{interval}' for Massive. Supported: {list(_TIMESPAN)}")
        return ts

    def _aggs_to_df(self, results: list, timespan: str) -> pd.DataFrame:
        cols = ["Open", "High", "Low", "Close", "Volume"]
        if not results:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(results)
        idx = pd.to_datetime(df["t"], unit="ms")   # tz-naive UTC
        if timespan == "day":
            idx = idx.dt.normalize()                # snap daily bars to midnight
        df = df.rename(columns={"o": "Open", "h": "High", "l": "Low",
                                "c": "Close", "v": "Volume"})
        df.index = idx
        df.index.name = "timestamp"
        return df[[c for c in cols if c in df.columns]]

    def _aggregates(self, ticker: str, start: str, end: str, interval: str) -> pd.DataFrame:
        mult, span = self._timespan(interval)
        path = f"/v2/aggs/ticker/{ticker}/range/{mult}/{span}/{_d(start)}/{_d(end)}"
        body = self._get(path, {"adjusted": "true", "sort": "asc", "limit": 50000})
        return self._aggs_to_df(body.get("results", []), span)

    # ── interface ────────────────────────────────────────────────────────────
    def get_underlying_bars(self, symbol, start, end, interval) -> pd.DataFrame:
        return self._aggregates(symbol, start, end, interval)

    def get_contract_bars(self, occ_symbol, start, end, interval) -> pd.DataFrame:
        ticker = occ_symbol if occ_symbol.startswith("O:") else f"O:{occ_symbol}"
        df = self._aggregates(ticker, start, end, interval)
        if df.empty:
            logger.warning(f"[options] Massive: no bars for {ticker} ({start}→{end}).")
        else:
            logger.info(f"[options] Massive bars {ticker}: {len(df)} rows")
        return df

    def get_chain(self, underlying, *, right=None, expiration_gte=None,
                  expiration_lte=None, strike_gte=None, strike_lte=None, as_of=None):
        params: dict = {"underlying_ticker": underlying, "limit": 1000}
        if right:
            params["contract_type"] = "call" if right.upper().startswith("C") else "put"
        if expiration_gte is not None:
            params["expiration_date.gte"] = _d(expiration_gte)
        if expiration_lte is not None:
            params["expiration_date.lte"] = _d(expiration_lte)
        if strike_gte is not None:
            params["strike_price.gte"] = strike_gte
        if strike_lte is not None:
            params["strike_price.lte"] = strike_lte
        if as_of is not None:
            # Point-in-time universe: returns contracts as they existed on this
            # date, INCLUDING ones that have since expired. Do NOT also send
            # `expired=true` — combined with as_of it excludes contracts that had
            # not yet expired on that date (i.e. everything we actually want).
            params["as_of"] = _d(as_of)
        elif expiration_lte is not None and _as_date(expiration_lte) < date.today():
            # Historical query without a point-in-time anchor → include expired.
            params["expired"] = "true"

        body = self._get("/v3/reference/options/contracts", params)
        contracts: list[OptionContract] = []
        for c in body.get("results", []):
            tkr = c.get("ticker", "")
            occ = tkr[2:] if tkr.startswith("O:") else tkr
            try:
                u, exp, r, strike = parse_occ_symbol(occ)
            except ValueError:
                continue
            contracts.append(OptionContract(
                symbol=occ, underlying=u, expiration=exp, strike=strike, right=r,
            ))
        if body.get("next_url"):
            logger.warning(
                "[options] Massive chain %s truncated at %d contracts (narrow the "
                "strike/expiration filters if you need more).", underlying, len(contracts))
        logger.info(f"[options] Massive chain {underlying} (as_of={as_of}): {len(contracts)} contracts")
        return contracts
