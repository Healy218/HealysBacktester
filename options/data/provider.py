# options/data/provider.py
"""
Vendor-agnostic options data interface.

Defines the contract every options data source (Alpaca now, Polygon/Massive
later) must implement, plus the lightweight value types passed around the
options subsystem. Keeping this abstract means the selection and backtest
layers never import a specific vendor SDK — swapping providers is a one-line
change in the runner.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import pandas as pd


@dataclass
class OptionContract:
    """A single option contract plus optional latest-snapshot enrichments."""
    symbol: str            # OCC symbol, e.g. "SPY260814C00746000"
    underlying: str
    expiration: date
    strike: float
    right: str             # "C" or "P"

    # Present only when the vendor supplies a snapshot (greeks / quote):
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    implied_vol: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    open_interest: Optional[int] = None

    @property
    def mid(self) -> Optional[float]:
        """Bid/ask midpoint, or None if either side is missing."""
        if self.bid is not None and self.ask is not None:
            return round((self.bid + self.ask) / 2.0, 4)
        return None

    def dte(self, as_of: date) -> int:
        """Calendar days to expiration from a reference date."""
        return (self.expiration - as_of).days


# OCC symbol: <root letters><YYMMDD><C|P><strike*1000, 8 digits>
_OCC_RE = re.compile(r"^(?P<root>[A-Z]+)(?P<exp>\d{6})(?P<right>[CP])(?P<strike>\d{8})$")


def parse_occ_symbol(symbol: str) -> tuple[str, date, str, float]:
    """Parse an OCC option symbol → (underlying, expiration, right, strike).

    Example: ``"SPY260814C00746000"`` → ``("SPY", date(2026, 8, 14), "C", 746.0)``.
    """
    m = _OCC_RE.match(symbol.strip().upper())
    if not m:
        raise ValueError(f"Not a valid OCC option symbol: {symbol!r}")
    root = m.group("root")
    exp = datetime.strptime(m.group("exp"), "%y%m%d").date()
    right = m.group("right")
    strike = int(m.group("strike")) / 1000.0
    return root, exp, right, strike


def build_occ_symbol(underlying: str, expiration: date, right: str, strike: float) -> str:
    """Build an OCC symbol from components (inverse of :func:`parse_occ_symbol`)."""
    r = right.upper()[:1]
    if r not in ("C", "P"):
        raise ValueError(f"right must be 'C' or 'P', got {right!r}")
    return f"{underlying.upper()}{expiration:%y%m%d}{r}{int(round(strike * 1000)):08d}"


class OptionsDataProvider(ABC):
    """Abstract options data source. Implemented once per vendor.

    All bar frames returned use the project-standard schema: a tz-naive
    ``DatetimeIndex`` and ``Open/High/Low/Close/Volume`` columns, so they drop
    straight into ``portfolio/simulator.run_backtest``.
    """

    @abstractmethod
    def get_underlying_bars(
        self, symbol: str, start: str, end: str, interval: str
    ) -> pd.DataFrame:
        """OHLCV bars for the underlying instrument."""

    @abstractmethod
    def get_chain(
        self,
        underlying: str,
        *,
        right: Optional[str] = None,
        expiration_gte: Optional[date] = None,
        expiration_lte: Optional[date] = None,
        strike_gte: Optional[float] = None,
        strike_lte: Optional[float] = None,
        as_of: Optional[date] = None,
    ) -> list[OptionContract]:
        """Contracts for the underlying, with greeks/quotes when the vendor has them.

        ``as_of`` requests a **point-in-time** chain (the contracts that existed
        on that date, including ones since expired) — required for historical
        backtests. Live-only vendors (e.g. Alpaca's free feed) ignore it.
        """

    @abstractmethod
    def get_contract_bars(
        self, occ_symbol: str, start: str, end: str, interval: str
    ) -> pd.DataFrame:
        """Historical OHLC(V) bars for a single option contract.

        Returns an empty frame (not an error) when the vendor has no history for
        the contract/window, so callers can distinguish "no data" from a failure.
        """
