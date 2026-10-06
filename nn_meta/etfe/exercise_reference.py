"""Exercise-reference extraction v2 from captured closing-auction trades.

Supersedes `closing_reference.official_close` (kept unchanged because capture roots pin that
module). Evidence from the full 2024 capture: on 2024-11-20 no venue published an `M` official
close while listing-venue closing-cross (`6`) prints were present, and Nasdaq reported QQQ's
closing cross under venue code `T` (NASDAQ Int) as well as `Q`.
"""
# Primary listing venue families (Alpaca SIP exchange codes).
LISTING={'SPY':{'P'},'VOO':{'P'},'QQQ':{'Q','T'}}


def official_close(symbol,rows):
    """Listing-venue `M` print; else listing-venue `6` closing cross. Conflicts stay unresolved."""
    venues=LISTING[symbol]
    m={r['p'] for r in rows if r['x'] in venues and 'M' in r['c']}
    six={r['p'] for r in rows if r['x'] in venues and '6' in r['c']}
    if len(m)>1:return dict(status='ambiguous',price=None,reason='conflicting_official_close')
    if m:
        price=next(iter(m))
        if six and price not in six:return dict(status='ambiguous',price=None,reason='closing_print_disagrees')
        return dict(status='resolved',price=price,reason='official_close' if six else 'official_close_without_closing_print')
    if len(six)>1:return dict(status='ambiguous',price=None,reason='conflicting_closing_print')
    if six:return dict(status='resolved',price=next(iter(six)),reason='closing_print_without_official_close')
    return dict(status='missing',price=None,reason='no_listing_closing_auction')
