"""Versioned paper execution concession; valuation and risk marks stay unchanged."""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from integrations.alpaca_paper.v6_pricing import mark_limit

POLICY = 'midpoint-concession-2pct-120s-v2'


def execution_limit(quote, *, now, after, side):
    if side not in ('buy', 'sell'):
        raise ValueError('execution side must be buy or sell')
    # Validate the same timestamps, sizes and spread as V1, using midpoint.
    market = mark_limit(dict(quote, mark=None), now=now, after=after)
    midpoint = Decimal(market['raw_mark'])
    factor, rounding = ((Decimal('1.02'), ROUND_CEILING) if side == 'buy'
                        else (Decimal('0.98'), ROUND_FLOOR))
    limit = (midpoint * factor).quantize(Decimal('0.01'), rounding=rounding)
    if limit <= 0:
        raise ValueError('adjusted midpoint cannot form a positive cent limit')
    return dict(market, limit_price=str(limit), execution_policy=POLICY,
                midpoint=str(midpoint), multiplier=str(factor), rounding=rounding)
