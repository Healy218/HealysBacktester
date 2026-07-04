# options/data/alpaca_provider.py
"""
Alpaca implementation of :class:`OptionsDataProvider`.

IMPORTANT — data availability (verified 2026-07-02):
  Alpaca's FREE options feed ("indicative") returns live chain snapshots with
  greeks + implied vol, but essentially NO historical bar history — a probe
  returned 0–4 daily bars even for 600-open-interest SPY calls over a 6-month
  window. Historical backtesting therefore needs Alpaca's paid OPRA options
  data subscription, or a deeper vendor (Polygon/Massive).

  This adapter still fully powers chain lookup + contract selection today;
  only ``get_contract_bars`` is history-limited on the free feed. When bars
  are unavailable it returns an EMPTY frame (not an error) so the runner can
  surface a clear "need a history-capable data source" message.
  See options/README.md.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Optional

import pandas as pd

from utils.logging_utils import setup_logging
from utils.error_handling import DataError
from utils.date_utils import ensure_tz_naive
from options.data.provider import OptionsDataProvider, OptionContract, parse_occ_symbol

logger = setup_logging(log_file="logs/backtester.log")


class AlpacaOptionsProvider(OptionsDataProvider):
    """Options data via alpaca-py's OptionHistoricalDataClient + stock loader."""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self._key = api_key or os.environ.get("ALPACA_API_KEY", "")
        self._secret = api_secret or os.environ.get("ALPACA_API_SECRET", "")
        if not self._key or not self._secret:
            raise DataError(
                "Alpaca API credentials not found. "
                "Set ALPACA_API_KEY and ALPACA_API_SECRET in your .env file."
            )
        self._client = None  # lazily created so import never requires alpaca-py

    def _option_client(self):
        if self._client is None:
            from alpaca.data.historical.option import OptionHistoricalDataClient
            self._client = OptionHistoricalDataClient(self._key, self._secret)
        return self._client

    # ── Underlying: reuse the existing stock loader ──────────────────────────
    def get_underlying_bars(self, symbol, start, end, interval) -> pd.DataFrame:
        from data.alpaca_loader import load_alpaca_bars
        return load_alpaca_bars(symbol, start, end, interval, self._key, self._secret)

    # ── Chain snapshot (with greeks / IV / quote) ────────────────────────────
    def get_chain(self, underlying, *, right=None, expiration_gte=None,
                  expiration_lte=None, strike_gte=None, strike_lte=None, as_of=None):
        from alpaca.data.requests import OptionChainRequest
        from alpaca.trading.enums import ContractType

        if as_of is not None:
            # Alpaca's chain snapshot is live-only; it cannot serve a historical
            # point-in-time chain. Use MassiveProvider for as_of queries.
            logger.debug("[options] Alpaca ignores as_of=%s (live snapshot only).", as_of)

        req: dict = {"underlying_symbol": underlying}
        if right:
            req["type"] = ContractType.CALL if right.upper().startswith("C") else ContractType.PUT
        if expiration_gte is not None:
            req["expiration_date_gte"] = expiration_gte
        if expiration_lte is not None:
            req["expiration_date_lte"] = expiration_lte
        if strike_gte is not None:
            req["strike_price_gte"] = strike_gte
        if strike_lte is not None:
            req["strike_price_lte"] = strike_lte

        try:
            snapshots = self._option_client().get_option_chain(OptionChainRequest(**req))
        except Exception as e:
            raise DataError(f"Alpaca option chain fetch failed for {underlying}: {e}") from e

        contracts: list[OptionContract] = []
        for sym, snap in snapshots.items():
            try:
                u, exp, r, strike = parse_occ_symbol(sym)
            except ValueError:
                continue
            greeks = getattr(snap, "greeks", None)
            quote = getattr(snap, "latest_quote", None)
            contracts.append(OptionContract(
                symbol=sym, underlying=u, expiration=exp, strike=strike, right=r,
                delta=getattr(greeks, "delta", None) if greeks else None,
                gamma=getattr(greeks, "gamma", None) if greeks else None,
                theta=getattr(greeks, "theta", None) if greeks else None,
                vega=getattr(greeks, "vega", None) if greeks else None,
                implied_vol=getattr(snap, "implied_volatility", None),
                bid=getattr(quote, "bid_price", None) if quote else None,
                ask=getattr(quote, "ask_price", None) if quote else None,
            ))
        logger.info(f"[options] Alpaca chain {underlying}: {len(contracts)} contracts")
        return contracts

    # ── Per-contract historical bars ─────────────────────────────────────────
    def get_contract_bars(self, occ_symbol, start, end, interval) -> pd.DataFrame:
        from alpaca.data.requests import OptionBarsRequest
        from data.alpaca_loader import _get_timeframe  # reuse interval → TimeFrame map

        empty = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        try:
            resp = self._option_client().get_option_bars(OptionBarsRequest(
                symbol_or_symbols=occ_symbol,
                timeframe=_get_timeframe(interval),
                start=datetime.fromisoformat(start),
                end=datetime.fromisoformat(end),
            ))
            df = resp.df
        except Exception as e:
            raise DataError(f"Alpaca option bars fetch failed for {occ_symbol}: {e}") from e

        if df is None or df.empty:
            logger.warning(
                f"[options] No historical bars for {occ_symbol} ({start}→{end}). "
                f"On Alpaca's free 'indicative' feed this is expected — enable OPRA "
                f"data or switch to Polygon/Massive for backtests (see options/README.md)."
            )
            return empty

        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(occ_symbol, level="symbol")
        df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                                "close": "Close", "volume": "Volume"})
        df = ensure_tz_naive(df)
        keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
        logger.info(f"[options] Alpaca bars {occ_symbol}: {df.shape[0]} rows")
        return df[keep]
