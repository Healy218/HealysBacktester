"""User-declared option-premium risk rules for the V6/V7 paper experiments."""
from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True)
class OptionRiskPolicy:
    generation: str
    premium_stop_fraction: float
    expiry_exit_before_close_minutes: int = 15
    price_basis: str = 'arithmetic_bid_ask_midpoint'

    def __post_init__(self):
        if (self.generation not in ('v6', 'v7')
                or isinstance(self.premium_stop_fraction, bool)
                or not isinstance(self.premium_stop_fraction, (int, float))
                or not math.isfinite(self.premium_stop_fraction)
                or not 0 < self.premium_stop_fraction < 1
                or self.expiry_exit_before_close_minutes != 15
                or self.price_basis != 'arithmetic_bid_ask_midpoint'):
            raise ValueError('Invalid option-premium paper risk policy')


V6_OPTION_RISK = OptionRiskPolicy('v6', .075)
V7_OPTION_RISK = OptionRiskPolicy('v7', .125)


def premium_stop(entry_midpoint, current_midpoint, policy):
    """Threshold on premium alone; fees and modeled slippage stay in the ledger.

    Calls and puts are both long options, so a decline in either midpoint is a
    loss. The entry reference is fixed for this purchased leg, not a high-water
    mark or the underlying stock price. A valid trigger quote also supplies the
    simulated sale midpoint; no second quote or broker fill is required.
    """
    if not isinstance(policy, OptionRiskPolicy):
        raise ValueError('Explicit option risk policy required')
    for value in (entry_midpoint, current_midpoint):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Finite midpoint references required')
    if entry_midpoint <= 0 or current_midpoint < 0:
        raise ValueError('Positive entry and nonnegative current midpoint required')
    threshold = entry_midpoint*(1-policy.premium_stop_fraction)
    # Multiplication avoids the rounding difference from computing 1-current/entry
    # at the exact user-selected threshold (e.g. 3.7 / 4 at 7.5%).
    return dict(triggered=current_midpoint <= threshold, entry_midpoint=float(entry_midpoint),
                current_midpoint=float(current_midpoint), trigger_midpoint=threshold,
                premium_return=current_midpoint/entry_midpoint-1, policy=asdict(policy))


def in_the_money(right, strike, underlying_price):
    if (right not in ('C', 'P') or any(isinstance(v, bool) or not isinstance(v, (int, float))
            or not math.isfinite(v) or v <= 0 for v in (strike, underlying_price))):
        raise ValueError('Explicit option right and positive observed underlying/strike required')
    return underlying_price > strike if right=='C' else underlying_price < strike


def strategy_only_simulator_config(config):
    """Remove the generic underlying loss stop without mutating frozen defaults."""
    from copy import deepcopy
    result = deepcopy(config)
    result['USE_STOP_LOSS'] = False
    result['STOP_LOSS_PERCENT'] = None
    result['ATR_SL_WINDOW'] = None
    result['USE_TRAILING_STOP'] = False
    return result
