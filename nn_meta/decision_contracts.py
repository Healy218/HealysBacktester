"""Decision-time option selection shared by richer features and their labels.

The existing archive records a contract's first observed *date*, not its
intraday listing time. This policy therefore uses contracts observed by the
end of the previous UTC date. It never treats a whole day's later prints as
evidence that a contract was available earlier that morning. Raw spot at the
decision close selects the strike; current snapshot Greeks are not historical
inputs. The policy is deliberately distinct from the legacy selector.
"""
from __future__ import annotations

from datetime import date, timedelta
import math

import pandas as pd

from options.data.provider import parse_occ_symbol
from options.selection.contract_selector import validate_spot_basis

POLICY_VERSION = "previous-date-raw-moneyness-v1"
BAR_NS = 15 * 60 * 1_000_000_000


def utc_stamp(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is None:
        raise ValueError("decision timestamps require an explicit timezone")
    return stamp.tz_convert("UTC")


class DecisionContractSelector:
    """Cache prior-date chains, then apply the current raw-spot band each call."""

    def __init__(self, provider, *, moneyness=0.0):
        if getattr(provider, "point_in_time_chain", False) is not True:
            raise ValueError("decision selection requires a declared point-in-time chain provider")
        if isinstance(moneyness, bool) or not math.isfinite(float(moneyness)) or moneyness <= -1:
            raise ValueError("invalid target moneyness")
        self.provider = provider
        self.moneyness = float(moneyness)
        self._chains = {}

    def select(self, symbol, *, as_of: date, right, raw_spot, target_dte):
        validate_spot_basis(raw_spot, "raw", require_raw=True)
        if type(as_of) is not date or right not in ("C", "P"):
            raise ValueError("selection needs a date and explicit C/P right")
        if isinstance(target_dte, bool) or not isinstance(target_dte, int) or target_dte < 0:
            raise ValueError("target DTE must be a nonnegative integer")
        symbol = symbol.upper()
        key = symbol, as_of, right, target_dte
        if key not in self._chains:
            earliest = as_of + timedelta(days=max(1, target_dte - 10))
            latest = as_of + timedelta(days=target_dte + 20)
            contracts = self.provider.get_chain(
                symbol, right=right, expiration_gte=earliest,
                expiration_lte=latest, as_of=as_of - timedelta(days=1))
            unique = {}
            for contract in contracts:
                occ = contract.symbol.upper().removeprefix("O:")
                root, expiration, parsed_right, strike = parse_occ_symbol(occ)
                if root != symbol:
                    member = getattr(self.provider, "historical_chain_member", None)
                    if not callable(member) or member(symbol, occ, as_of - timedelta(days=1)) is not True:
                        raise ValueError("OCC root mismatch lacks prior-date catalogue alias evidence")
                if (contract.underlying.upper() != symbol or contract.right != right
                        or parsed_right != right or contract.expiration != expiration
                        or contract.strike != strike or not earliest <= expiration <= latest):
                    raise ValueError("chain contract identity or requested bounds mismatch")
                identity = (contract.underlying, expiration, right, strike)
                if occ in unique and unique[occ][0] != identity:
                    raise ValueError("conflicting chain contract identity")
                unique[occ] = identity, contract
            self._chains[key] = [unique[k][1] for k in sorted(unique)]
        # Cache the entire time-bounded chain. A previous intraday spot must
        # never pin the strike band for later, potentially large price moves.
        eligible = [c for c in self._chains[key]
                    if raw_spot * .85 <= c.strike <= raw_spot * 1.15]
        if not eligible:
            return None
        expiry = min({c.expiration for c in eligible},
                     key=lambda value: (abs((value - as_of).days - target_dte), value))
        target = raw_spot * (1.0 + self.moneyness)
        return min((c for c in eligible if c.expiration == expiry),
                   key=lambda c: (abs(c.strike - target), c.strike,
                                  c.symbol.upper().removeprefix("O:")))

    def request(self, symbol, *, signal_bar_open, right, raw_spot, target_dte,
                consumer_ids=()):
        """Select first, then describe its trailing closed-bar tick window.

        No option OHLCV, execution outcome, P&L or future quote is queried.
        Unselected requests are explicit records; callers must not manufacture
        a placeholder contract or zero-valued market observations.
        """
        start = utc_stamp(signal_bar_open)
        if start.value % BAR_NS:
            raise ValueError("signal bar open must align to the 15-minute UTC grid")
        decision = start + pd.Timedelta(minutes=15)
        contract = self.select(symbol, as_of=decision.date(), right=right,
                               raw_spot=raw_spot, target_dte=target_dte)
        return {
            "symbol": symbol.upper(),
            "contract": contract.symbol.upper().removeprefix("O:") if contract else None,
            "window_start_ns": int(start.value), "window_end_ns": int(decision.value),
            "decision_close_ns": int(decision.value), "selected_at_ns": int(decision.value),
            "raw_spot_available_ns": int(decision.value), "raw_spot": float(raw_spot),
            "chain_available_ns": int(decision.normalize().value),
            "consumer_ids": list(consumer_ids),
            "selection_policy": POLICY_VERSION, "right": right, "target_dte": target_dte,
            "status": "selected" if contract else "unselected",
            "reason": None if contract else "no_prior_date_contract_in_selection_band",
        }
