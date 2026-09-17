"""User-selected midpoint convention for simulated option fills and marks."""
import math

MIDPOINT_POLICY = 'option-arithmetic-midpoint-paper-v2'


def option_midpoint(quote):
    """Use the arithmetic average of the contemporaneous bid and ask.

    Auxiliary provider mid/last fields never override these sides. The original
    quote remains with the fill record. This is the user's simulated pricing
    convention, not evidence that a broker order executed at this price.
    """
    bid = quote.get('bid', quote.get('bid_price'))
    ask = quote.get('ask', quote.get('ask_price'))
    def valid_number(value):
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    if not valid_number(bid) or not valid_number(ask) or not 0 < bid <= ask:
        raise ValueError('Positive finite uncrossed bid/ask required for midpoint')
    price = float(bid / 2 + ask / 2)
    return dict(price=price, bid=float(bid), ask=float(ask), pricing_policy=MIDPOINT_POLICY,
                price_source='computed_bid_ask_average',
                simulated=True)
