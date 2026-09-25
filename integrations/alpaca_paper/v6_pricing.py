"""Pure mark-limit and whole-contract sizing for a future V6 paper order bridge."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP


def _stamp(value) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("quote timestamp must be timezone aware")
    return parsed.astimezone(timezone.utc)


def mark_limit(quote: dict, *, now: datetime, after: datetime) -> dict:
    """Prefer a provider mark; otherwise use a fresh bid/ask midpoint.

    Last trade is only context. A present but invalid mark blocks an order
    instead of silently substituting a different execution price.
    """
    if now.tzinfo is None or after.tzinfo is None:
        raise ValueError("decision and receipt clocks must be aware")
    bid, ask = Decimal(str(quote["bid"])), Decimal(str(quote["ask"]))
    if not bid.is_finite() or not ask.is_finite() or not 0 < bid <= ask:
        raise ValueError("invalid bid/ask")
    bid_size, ask_size = int(quote["bid_size"]), int(quote["ask_size"])
    if bid_size <= 0 or ask_size <= 0:
        raise ValueError("empty displayed quote")
    received = _stamp(quote["received_at"])
    sip = datetime.fromtimestamp(int(quote["sip_timestamp_ns"]) / 1e9, timezone.utc)
    if not after <= sip <= received <= now.astimezone(timezone.utc) or (now - sip).total_seconds() > 30:
        raise ValueError("stale or pre-decision quote")
    explicit = quote.get("mark")
    if explicit is None:
        mark, source = (bid + ask) / 2, "bid_ask_midpoint"
    else:
        mark, source = Decimal(str(explicit)), "provider_mark"
        if not mark.is_finite() or not bid <= mark <= ask:
            raise ValueError("provider mark is outside fresh bid/ask")
    if mark <= 0:
        raise ValueError("nonpositive mark")
    rounded = mark.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded <= 0 or rounded > ask:
        raise ValueError("mark cannot form a valid cent limit")
    return {"limit_price": str(rounded), "raw_mark": str(mark), "mark_source": source,
            "bid": str(bid), "ask": str(ask), "ask_size": ask_size,
            "last_price": str(quote["last"]) if quote.get("last") is not None else None,
            "quote_at": sip.isoformat(), "received_at": received.isoformat()}


def entry_preview(*, options_buying_power: str, size_fraction: float, mark: dict) -> dict:
    """Cap a long-option preview at V6 fraction, broker BP and ask size."""
    buying_power = Decimal(options_buying_power)
    fraction = Decimal(str(size_fraction))
    price = Decimal(mark["limit_price"])
    if (not buying_power.is_finite() or buying_power <= 0 or
            not fraction.is_finite() or not 0 < fraction <= Decimal("0.1") or
            not price.is_finite() or price <= 0):
        raise ValueError("invalid account buying power, V6 fraction or mark")
    budget = buying_power * fraction
    contract_cost = price * 100
    affordable = int((budget / contract_cost).to_integral_value(rounding=ROUND_DOWN))
    quantity = min(affordable, int(mark["ask_size"]))
    return {"budget_usd": str(budget), "contract_cost_usd": str(contract_cost),
            "affordable_contracts": affordable, "displayed_ask_size": int(mark["ask_size"]),
            "preview_contracts": quantity, "limit_price": mark["limit_price"],
            "mark_source": mark["mark_source"], "order_submission_enabled": False}
