"""Dollar cost scenarios for index options (spx0).

Percent-of-premium costs (the equity pool's model) understate index-option
friction on a 0.30 premium: fees are per contract and spreads are in points.
Both are explicit here, base and stressed, and flow into ``net_return`` so the
gate sees them. Multiplier is $100/point for SPX/NDX.
"""
from __future__ import annotations

from dataclasses import dataclass

MULTIPLIER = 100.0


@dataclass(frozen=True)
class IndexCostScenario:
    name: str = "base"
    fee_per_contract: float = 1.30        # broker + exchange + index fee, per side
    half_spread_points: float = 0.05      # on premiums <= 1.00
    spread_scale_above_1: float = 0.05    # + this × (premium − 1) above 1.00

    def half_spread(self, premium: float) -> float:
        extra = max(float(premium) - 1.0, 0.0) * self.spread_scale_above_1
        return self.half_spread_points + extra

    def side_cost_points(self, premium: float) -> float:
        """Cost per contract per side, in index points."""
        return self.half_spread(premium) + self.fee_per_contract / MULTIPLIER


BASE = IndexCostScenario()
STRESSED = IndexCostScenario(name="stressed", fee_per_contract=2.00,
                             half_spread_points=0.15, spread_scale_above_1=0.10)


def net_return(entry_price: float, exit_price: float, costs: IndexCostScenario = BASE
               ) -> float:
    """Return on premium paid, after per-side spread and fees in points.
    ``entry_price``/``exit_price`` are the modeled fill prints."""
    if float(entry_price) <= 0:
        raise ValueError("entry premium must be positive")
    paid = float(entry_price) + costs.side_cost_points(entry_price)
    got = float(exit_price) - costs.side_cost_points(exit_price)
    return got / paid - 1.0


def gross_return(entry_price: float, exit_price: float) -> float:
    if entry_price <= 0:
        raise ValueError("entry premium must be positive")
    return float(exit_price) / float(entry_price) - 1.0


def short_margin(entry_price: float, stop_frac: float) -> float:
    """Margin posted against a sold contract: the max planned loss, set by the
    premium stop at ``stop_frac × entry`` (SPX0_SPEC "Second design round")."""
    if entry_price <= 0:
        raise ValueError("entry premium must be positive")
    if stop_frac <= 1:
        raise ValueError("a short's stop_frac must exceed 1")
    return (float(stop_frac) - 1.0) * float(entry_price)


def gross_return_short(entry_price: float, exit_price: float, margin: float) -> float:
    """Seller's raw return on posted margin: −1 means the stop fired exactly at
    its level; below −1 is gap/settlement past the stop (real, kept)."""
    if margin <= 0:
        raise ValueError("margin must be positive")
    return (float(entry_price) - float(exit_price)) / float(margin)


def vertical_margin(width: float, credit: float) -> float:
    """Margin posted against a credit vertical: the max possible loss by
    CONSTRUCTION — settlement pays at most the strike width, so width − credit
    is the true worst case (no stop needed, unlike a naked short)."""
    if width <= 0:
        raise ValueError("strike width must be positive")
    if not 0 < credit < width:
        raise ValueError("credit must lie in (0, width) for a credit vertical")
    return float(width) - float(credit)


def gross_return_vertical(credit: float, exit_debit: float, margin: float) -> float:
    """Seller's raw return on posted margin; ``exit_debit`` is what closing
    costs (market buy-back net of the wing sale, or settlement in [0, width])."""
    if margin <= 0:
        raise ValueError("margin must be positive")
    return (float(credit) - float(exit_debit)) / float(margin)


def package_cost_points(net_premium: float, costs: IndexCostScenario = BASE) -> float:
    """One side of a two-leg PACKAGE: index verticals trade the complex order
    book as a single net-premium market, so the crossing pays ONE half-spread
    on the net (not each leg's full-premium spread — that double-charges an
    ATM spread ~10× reality) plus both contracts' fees."""
    return costs.half_spread(abs(float(net_premium))) + 2 * costs.fee_per_contract / MULTIPLIER


def net_return_vertical(credit: float, exit_debit: float, margin: float,
                        costs: IndexCostScenario = BASE, *,
                        settled: bool = False) -> float:
    """Credit-vertical return on posted margin after package costs: the net
    credit pays one package crossing at entry; a market exit pays another on
    the net debit, while cash settlement pays the net intrinsic with no
    crossing."""
    if float(margin) <= 0:
        raise ValueError("margin must be positive")
    got = float(credit) - package_cost_points(credit, costs)
    debit = float(exit_debit)
    if not settled:
        debit += package_cost_points(exit_debit, costs)
    return (got - debit) / float(margin)


def net_return_short(entry_price: float, exit_price: float, margin: float,
                     costs: IndexCostScenario = BASE, *, settled: bool = False) -> float:
    """Seller's return on posted margin after costs: the premium received nets
    the entry-side spread and fee; a market buyback pays the exit side too,
    while cash settlement (``settled=True``) pays intrinsic with no crossing."""
    if float(entry_price) <= 0:
        raise ValueError("entry premium must be positive")
    if float(margin) <= 0:
        raise ValueError("margin must be positive")
    got = float(entry_price) - costs.side_cost_points(entry_price)
    paid = float(exit_price) + (0.0 if settled else costs.side_cost_points(exit_price))
    return (got - paid) / float(margin)
