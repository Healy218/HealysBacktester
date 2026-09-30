"""Three fixed-midpoint paper limits; marks and risk valuation stay unchanged."""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from integrations.alpaca_paper.v6_pricing import mark_limit

POLICY = 'midpoint-step-5-10-12.5pct-v4'
WAITS = (30, 30, 60)
CONCESSIONS = (Decimal(".05"), Decimal(".10"), Decimal(".125"))


def step_limit(midpoint, side, step):
    if side not in ('buy', 'sell') or step not in range(len(CONCESSIONS)):
        raise ValueError('Invalid step or side')
    midpoint = Decimal(str(midpoint))
    if not midpoint.is_finite() or midpoint <= 0:
        raise ValueError('Invalid anchor midpoint')
    concession = CONCESSIONS[step]
    factor = 1 + concession if side == 'buy' else 1 - concession
    value = (midpoint * factor).quantize(Decimal('.01'), rounding=(
        ROUND_CEILING if side == 'buy' else ROUND_FLOOR))
    if value <= 0:
        raise ValueError('Step cannot form a positive cent limit')
    return str(value)


def execution_limit(quote, *, now, after, side):
    market = mark_limit(dict(quote, mark=None), now=now, after=after)
    midpoint = market['raw_mark']
    return dict(market, midpoint=midpoint, execution_policy=POLICY,
                limit_price=step_limit(midpoint, side, 0),
                step_limits=[step_limit(midpoint, side, i) for i in range(len(CONCESSIONS))])
