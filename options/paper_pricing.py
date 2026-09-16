"""User-selected midpoint convention for simulated option fills and marks."""
import math

MIDPOINT_POLICY = 'option-midpoint-paper-v1'


def option_midpoint(quote):
    """Retain both sides; use a supplied mid when valid, else their average.

    A supplied mid is validated within the current spread. Different supplied
    aliases must agree. A null alias is absent; malformed values fail closed.
    This is a paper pricing convention, not evidence of a trade at that price.
    """
    bid = quote.get('bid', quote.get('bid_price'))
    ask = quote.get('ask', quote.get('ask_price'))
    def valid_number(value):
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    if not valid_number(bid) or not valid_number(ask) or not 0 < bid <= ask:
        raise ValueError('Positive finite uncrossed bid/ask required for midpoint')
    supplied = [(key, quote[key]) for key in ('mid', 'midpoint', 'mid_price', 'midpoint_price')
                if quote.get(key) is not None]
    for key, value in supplied:
        if not valid_number(value) or not bid <= value <= ask:
            raise ValueError('Provider midpoint must be finite and inside bid/ask')
    if supplied and any(value != supplied[0][1] for _, value in supplied):
        raise ValueError('Conflicting provider midpoint fields')
    price = float(supplied[0][1]) if supplied else float(bid / 2 + ask / 2)
    return dict(price=price, bid=float(bid), ask=float(ask), pricing_policy=MIDPOINT_POLICY,
                price_source=('provider:' + supplied[0][0]) if supplied else 'computed_bid_ask_average',
                simulated=True)
