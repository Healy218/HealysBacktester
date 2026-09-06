# options/selection/contract_selector.py
"""
Contract selection for single-leg options strategies.

Given a chain (``list[OptionContract]``) and a target profile, pick one
contract: nearest to a target days-to-expiration, then nearest to a target
absolute delta (when greeks are available) or a target moneyness (fallback).

Pure functions — no vendor SDK, no I/O — so they are fully unit-testable.
"""
from __future__ import annotations

from datetime import date
from typing import Optional
import math

from options.data.provider import OptionContract


def validate_spot_basis(spot, spot_basis=None, *, require_raw=False):
    """Strict pipeline callers declare raw spot before comparing OCC strikes.

    Legacy scalar-only callers cannot establish source lineage. A declared
    adjusted basis is always rejected; new research execution requires raw.
    """
    if spot_basis is not None and spot_basis != "raw":
        raise ValueError("listed option strikes require raw contemporaneous spot")
    if require_raw and spot_basis != "raw":
        raise ValueError("option selection requires explicit raw spot price basis")
    if spot is not None and (isinstance(spot, bool) or not math.isfinite(float(spot)) or float(spot) <= 0):
        raise ValueError("option selection spot must be finite and positive")
    if require_raw and spot is None:
        raise ValueError("raw spot is required for option selection")


def _nearest_expiration(contracts: list[OptionContract], target_dte: int, as_of: date):
    """The available expiration whose DTE is closest to ``target_dte``."""
    expirations = sorted({c.expiration for c in contracts})
    if not expirations:
        return None
    return min(expirations, key=lambda e: abs((e - as_of).days - target_dte))


def _filter(contracts, right: str, exp) -> list[OptionContract]:
    r = right.upper()[:1]
    return [c for c in contracts if c.right == r and c.expiration == exp]


def select_by_dte_and_delta(
    contracts: list[OptionContract],
    *,
    right: str,
    target_dte: int = 30,
    target_delta: float = 0.50,
    as_of: Optional[date] = None,
) -> Optional[OptionContract]:
    """Pick the contract nearest ``target_dte``, then nearest |delta| to target.

    Returns ``None`` when the chain carries no greeks (caller should fall back
    to :func:`select_by_dte_and_moneyness`).
    """
    as_of = as_of or date.today()
    exp = _nearest_expiration([c for c in contracts if c.right == right.upper()[:1]],
                              target_dte, as_of)
    if exp is None:
        return None
    pool = [c for c in _filter(contracts, right, exp) if c.delta is not None]
    if not pool:
        return None
    return min(pool, key=lambda c: abs(abs(c.delta) - target_delta))


def select_by_dte_and_moneyness(
    contracts: list[OptionContract],
    *,
    right: str,
    spot: float,
    target_dte: int = 30,
    moneyness: float = 0.0,
    as_of: Optional[date] = None,
    spot_basis: Optional[str] = None,
    require_raw_spot: bool = False,
) -> Optional[OptionContract]:
    """Fallback selector by strike distance from spot.

    ``moneyness`` is a fraction of spot: ``0.0`` → at-the-money, ``+0.02`` → a
    strike ~2% above spot, etc. Used when the chain lacks greeks.
    """
    validate_spot_basis(spot, spot_basis, require_raw=require_raw_spot)
    if isinstance(moneyness, bool) or not math.isfinite(float(moneyness)) or moneyness <= -1:
        raise ValueError("target moneyness must be finite and greater than -1")
    as_of = as_of or date.today()
    exp = _nearest_expiration([c for c in contracts if c.right == right.upper()[:1]],
                              target_dte, as_of)
    if exp is None:
        return None
    pool = _filter(contracts, right, exp)
    if not pool:
        return None
    target_strike = spot * (1.0 + moneyness)
    return min(pool, key=lambda c: abs(c.strike - target_strike))


def select_contract(
    contracts: list[OptionContract],
    *,
    right: str,
    spot: Optional[float] = None,
    target_dte: int = 30,
    target_delta: float = 0.50,
    moneyness: float = 0.0,
    as_of: Optional[date] = None,
    spot_basis: Optional[str] = None,
    require_raw_spot: bool = False,
) -> Optional[OptionContract]:
    """Convenience: prefer delta-based selection, fall back to moneyness by strike.

    When neither greeks nor a spot price are available, returns the median-strike
    contract of the nearest expiration as a last resort.
    """
    validate_spot_basis(spot, spot_basis, require_raw=require_raw_spot)
    pick = select_by_dte_and_delta(
        contracts, right=right, target_dte=target_dte,
        target_delta=target_delta, as_of=as_of,
    )
    if pick is not None:
        return pick

    if spot is not None:
        return select_by_dte_and_moneyness(
            contracts, right=right, spot=spot, target_dte=target_dte,
            moneyness=moneyness, as_of=as_of,
            spot_basis=spot_basis, require_raw_spot=require_raw_spot,
        )

    # Last resort: no greeks and no spot — take the median strike of nearest expiry.
    as_of = as_of or date.today()
    exp = _nearest_expiration([c for c in contracts if c.right == right.upper()[:1]],
                              target_dte, as_of)
    if exp is None:
        return None
    pool = sorted(_filter(contracts, right, exp), key=lambda c: c.strike)
    return pool[len(pool) // 2] if pool else None
