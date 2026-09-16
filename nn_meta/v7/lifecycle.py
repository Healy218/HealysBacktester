"""Retrospective gap explanations, separate from causal execution admission."""
from datetime import date
from urllib.parse import urlsplit


def classify_gaps(gaps, review):
    if review.get('schema') != 'v7-reviewed-lifecycle-facts-v1':
        raise ValueError('Reviewed lifecycle facts required')
    events = review['events']
    for event in events:
        start, end = (date.fromisoformat(event[k]) for k in ('first_session', 'last_session'))
        date.fromisoformat(event['document_date'])
        if (start > end or not event['security_id'] or not event['symbol']
                or event['kind'] not in ('cash_merger', 'stock_successor', 'otc_successor', 'trading_halt')
                or urlsplit(event['source_url']).scheme != 'https'
                or event.get('point_in_time_admitted') is not False
                or event.get('held_positions_resolved') is not False):
            raise ValueError('Retrospective review cannot admit execution or point-in-time availability')
    if gaps.duplicated(['security_id', 'membership_ticker', 'date']).any():
        raise ValueError('Duplicate missing security session')
    rows = []
    for gap in gaps.to_dict('records'):
        hits = [e for e in events if e['symbol'] == gap['membership_ticker']
                and e['security_id'] == gap['security_id']
                and e['first_session'] <= gap['date'] <= e['last_session']]
        if len(hits) > 1:
            raise ValueError('Overlapping lifecycle explanations')
        event = hits[0] if hits else {}
        rows.append({**gap, 'explanation': event.get('kind', 'unexplained'),
                     'source_url': event.get('source_url'), 'successor': event.get('successor'),
                     'point_in_time_admitted': False, 'held_positions_resolved': False})
    return rows
