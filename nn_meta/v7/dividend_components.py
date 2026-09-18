"""Reconcile every held cash leaf to its single compiled price adjustment."""
from collections import defaultdict
from decimal import Decimal

from nn_meta.v7.storage import identity
from nn_meta.v7.stock_cash import validate_cash_event


def validate_components(actions, events, calendar, settlement_calendar=None):
    sources = {a['action']['event_id']: a for a in actions if a['category'] == 'cash'}
    if len(sources) != sum(a['category'] == 'cash' for a in actions):
        raise ValueError('Duplicate cash price source')
    grouped = defaultdict(list)
    seen = set()
    for event in events:
        validate_cash_event(event, calendar, settlement_calendar=settlement_calendar)
        source = sources.get(event['compiled_event_id'])
        if (source is None or event['event_id'] in seen
                or event['event_id'] != 'stock-cash:'+identity({k:v for k,v in event.items() if k!='event_id'})
                or event['source_identity'] != identity(source)
                or event['replaces'] != source['replaces']
                or event['security_id'] != source['security_id']
                or event['symbol'] != source['symbol']):
            raise ValueError('Cash component differs from its price source')
        seen.add(event['event_id']); grouped[event['compiled_event_id']].append(event)
    for key, leaves in grouped.items():
        source = sources[key]
        if sum((Decimal(e['cash_per_share']) for e in leaves), Decimal(0)) != Decimal(source['cash_amount']):
            raise ValueError('Held payments do not sum to the price distribution')
        payments = source.get('reviewed_payments')
        if payments is None:
            if len(leaves) != 1 or any('dividend_component_index' in e for e in leaves):
                raise ValueError('Legacy cash source requires exactly one entitlement')
        else:
            if (len(leaves) != len(payments) or
                    {e.get('dividend_component_index') for e in leaves} != set(range(len(payments)))):
                raise ValueError('Every named payment must occur exactly once')
            for e in leaves:
                p = payments[e['dividend_component_index']]
                if (e.get('dividend_component_count') != len(payments)
                        or e.get('dividend_component_name') != p['name']
                        or e['record_date'] != p['record_date'] or e['pay_date'] != p['pay_date']
                        or Decimal(e['cash_per_share']) != Decimal(p['cash_per_share'])
                        or e.get('date_evidence_identity') != p['terms_evidence_identity']):
                    raise ValueError('Payment terms differ from primary review')
    return grouped
