"""Robinhood retail, single-leg option fee estimates; unrelated to research costs.

Sources checked 2026-09-10:
https://robinhood.com/us/en/support/articles/trading-fees-on-robinhood/
https://cdn.robinhood.com/assets/robinhood/legal/RHF%20Fee%20Schedule.pdf
PDF revision 20260831-5886092-18771991. One execution per side is assumed;
actual execution-level rounding/tiering can differ from a position-level estimate.
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import os

VERSION = 'robinhood-retail-20260831-checked-20260910'
SOURCE = 'https://robinhood.com/us/en/support/articles/trading-fees-on-robinhood/'
INDEX_ROOTS = frozenset('SPX SPXW VIX VIXW XSP DJX MRUT RUT RUTW NDX NDXP XND MGTN CBTX MBTX'.split())
CENT = Decimal('.01')


def profile():
    raw = os.environ.get('ROBINHOOD_GOLD', '').lower()
    gold = True if raw in ('1','true','yes') else False if raw in ('0','false','no') else None
    return dict(version=VERSION, gold=gold, source=SOURCE)


def _decimal(value):
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise ValueError('Expected a finite nonnegative amount')
    return number


def _rounded(value):
    # RH PDF footnotes: sub-cent CAT and TAF totals round DOWN to zero.
    return Decimal(0) if value < CENT else value.quantize(CENT, rounding=ROUND_HALF_UP)


def side_fees(contract, quantity, premium, side, *, gold=None):
    """Estimate one execution. Contract fees do not depend on moneyness."""
    from options.data.provider import parse_occ_symbol
    if side not in ('buy', 'sell') or not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
        raise ValueError('Specify buy/sell and a positive integer quantity')
    root = parse_occ_symbol(contract)[0]
    p, qty = _decimal(premium), Decimal(quantity)
    index = root in INDEX_ROOTS
    if index and gold is None:
        raise ValueError('Gold status is required for index-option fees')
    exchange = Decimal(0)
    if root in ('SPX', 'SPXW'):
        exchange = Decimal('.57' if p < 1 else '.66') if root == 'SPX' else Decimal('.50' if p < 1 else '.59')
    elif root in ('VIX', 'VIXW'):
        exchange = Decimal('.10' if p <= Decimal('.10') else '.25' if p < 1 else '.40' if p < 2 else '.45')
    elif root in ('XSP','DJX','MRUT'):
        exchange = Decimal(0) if quantity < 10 else Decimal('.07')
    elif root in ('RUT','RUTW'):
        exchange = Decimal('.18')
    elif root in ('NDX','NDXP'):
        exchange = Decimal('.25') if p < 25 else Decimal('.50')
    elif root in ('MGTN','CBTX','MBTX'):
        exchange = Decimal({'MGTN':'.16','CBTX':'.50','MBTX':'.25'}[root])
    fees = dict(orf_occ=qty * Decimal('.04'), cat=_rounded(qty * Decimal('.0003')),
                broker=qty * Decimal('.35' if gold else '.50') if index else Decimal(0),
                exchange=qty * exchange, sec=Decimal(0), taf=Decimal(0))
    if side == 'sell' and not index:
        fees['sec'] = (qty * p * 100 * Decimal('20.60') / Decimal(1000000)).quantize(CENT, rounding=ROUND_CEILING)
        fees['taf'] = min(Decimal('9.79'), _rounded(qty * Decimal('.00329')))
    fees['total'] = sum(fees.values()).quantize(CENT)
    return {k:float(v) for k,v in fees.items()}


def accounting(context, quantity, entry_price, exit_price=None):
    """Unknown fills stay unknown. Values are estimates, never broker receipts."""
    if not quantity or entry_price is None:
        return None
    policy = context.get('broker_fees') or profile()
    if policy.get('version') != VERSION:
        return None
    try:
        entry = side_fees(context['contract'], quantity, entry_price, 'buy', gold=policy.get('gold'))
        premium = _decimal(entry_price) * quantity * 100
        cost = premium + _decimal(entry['total'])
        result = dict(entry_fees=entry['total'], entry_cost=float(cost), schedule=VERSION)
        if exit_price is not None:
            closing = side_fees(context['contract'], quantity, exit_price, 'sell', gold=policy.get('gold'))
            proceeds = _decimal(exit_price) * quantity * 100 - _decimal(closing['total'])
            pnl = proceeds - cost
            result.update(exit_fees=closing['total'], net_proceeds=float(proceeds), net_pnl=float(pnl),
                          net_return=float(pnl / cost) if cost else None)
        return result
    except (ValueError, KeyError):
        return None


def entry_line(context, quantity, premium):
    a = accounting(context, quantity, premium)
    if a is None:
        return ''
    return f"Estimated entry cost: ${a['entry_cost']:,.2f} incl. ${a['entry_fees']:.2f} fees"


def quote_pnl_line(context, quantity, premium, quote, now=None):
    """Liquidation estimate uses a fresh bid, not a midpoint or theoretical delta."""
    if not quote:
        return ''
    now = now or datetime.now(timezone.utc)
    try:
        ts = datetime.fromisoformat(quote['ts'].replace('Z','+00:00'))
        age = (now - ts).total_seconds()
        bid, ask = _decimal(quote['bid']), _decimal(quote['ask'])
        if not 0 <= age <= 180 or bid <= 0 or ask < bid:
            return ''
        a = accounting(context, quantity, premium, bid)
    except (ValueError, KeyError, TypeError, ArithmeticError):
        return ''
    if a is None:
        return ''
    return (f"Estimated net P/L at bid: ${a['net_pnl']:+,.2f} ({a['net_return']:+.1%})"
            f" · includes entry/exit fees ${a['entry_fees'] + a['exit_fees']:.2f}")
