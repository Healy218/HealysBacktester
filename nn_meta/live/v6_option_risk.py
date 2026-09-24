"""Option-quote risk checks independent of the slower underlying signal scan."""
import pandas as pd

from options.paper_pricing import MIDPOINT_POLICY, option_midpoint
from options.paper_risk import V6_OPTION_RISK, premium_stop, in_the_money
from nn_meta.live.v6_portfolio import checked_quote
from nn_meta.live.v6_option_sessions import expiry_cutoff


def monitor_option_position(book, position, market, *, clock, alerts, calendar=None,
                            underlying_mark=None):
    """Sell premium stops and ITM expiry exits at the validated trigger midpoint.

    The caller may run this without recalculating indicators or downloading stock
    bars. An underlying observation is needed only for expiry ITM classification.
    The existing OTM roll path is left to the strategy/contract-selection worker.
    """
    key = position['key']
    if position['state']=='roll_pending':
        return {'key':key, 'status':'cash_waiting_for_roll'}
    if position['state']=='exit_due':
        book.settle(key, quote_loader=market.execution_quote, clock=clock, alerts=alerts)
        return {'key':key, 'status':'exit_retried'}
    if position.get('pricing_policy')!=MIDPOINT_POLICY:
        raise ValueError('Option risk monitoring requires the audited arithmetic midpoint transition')
    after = pd.Timestamp(position['opened_at'])
    quote = market.execution_quote(position['contract'], after=after)
    now = clock()
    checked_quote(quote, position['contract'], now, after)
    current = option_midpoint(quote)
    assessment = premium_stop(position['entry_reference']['price'], current['price'], V6_OPTION_RISK)
    reason = None
    evidence = {'quote':quote, 'assessment':assessment}
    if assessment['triggered']:
        reason = 'option midpoint loss reached 7.5% from entry'
    elif calendar is not None and now >= expiry_cutoff(position['contract'], calendar):
        if underlying_mark is None:
            return {'key':key, 'status':'expiry_underlying_required', 'assessment':assessment}
        spot = underlying_mark(position['symbol'], now)
        now = clock()
        if (not isinstance(spot,dict) or type(spot.get('sip_timestamp')) is not int
                or not 0 <= now.value-spot['sip_timestamp'] <= 30_000_000_000):
            raise ValueError('ITM expiry classification needs a fresh causal underlying mark')
        from options.data.provider import parse_occ_symbol
        _,_,right,strike = parse_occ_symbol(position['contract'])
        if in_the_money(right,strike,spot['price']):
            reason = 'ITM option expiry: 15-minute pre-close exit'
            evidence['underlying_mark'] = spot
        else:
            return {'key':key, 'status':'otm_expiry', 'assessment':assessment}
    if reason is None:
        return {'key':key, 'status':'holding', 'assessment':assessment,
                'observed':{'contract':position['contract'], 'rolls':int(position.get('rolls',0)),
                    'opened_at':position['opened_at'], 'quote_at_ns':int(quote['sip_timestamp_ns']),
                    'quote_received_at':quote['received_at'], 'assessed_at':now.isoformat()}}
    triggered = book.trigger(key, kind='exit', reason=reason,
        at=pd.Timestamp(quote['sip_timestamp_ns'], tz='UTC'), alerts=alerts,
        evidence=evidence, expected_leg=position)
    if not triggered:
        return {'key':key, 'status':'position_changed', 'assessment':assessment}
    # This is a simulated midpoint sale. The already validated trigger quote
    # supplies its price; no second provider request or limit-fill proof is needed.
    book.settle(key, quote_loader=lambda *a, **k: quote, clock=clock, alerts=alerts)
    return {'key':key, 'status':'exit_triggered', 'reason':reason, 'assessment':assessment}
