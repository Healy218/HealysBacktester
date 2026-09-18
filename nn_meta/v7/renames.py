"""Finite primary-reviewed ticker changes of unchanged common shares.

These events have no chart factor or cash entitlement. They resolve their exact
provider record only; simultaneous mergers/distributions remain separate gates.
"""
from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.daily_identities import EXCHANGES
from nn_meta.v7.storage import identity


def validate_rename(event):
    required = ('security_id', 'share_class_figi', 'old_symbol', 'new_symbol',
                'review_identity', 'evidence_identity', 'prior_date', 'effective_date')
    if (event.get('schema') != 'v7-reviewed-common-share-rename-v1'
            or any(not isinstance(event.get(k), str) or not event[k] for k in required)
            or event['old_symbol'] == event['new_symbol']
            or event.get('share_quantity_factor') != 1 or event.get('cash_delta') != 0
            or event.get('option_deliverables_admitted') is not False
            or type(event.get('effective_ns')) is not int
            or type(event.get('available_ns')) is not int
            or event['available_ns'] > event['effective_ns']
            or event.get('event_id') != 'rename:' + event['review_identity']):
        raise ValueError('Reviewed unchanged common-share rename required')
    return event


def require_rename_history(event, history):
    validate_rename(event)
    facts = history[history.security_id.eq(event['security_id'])].set_index('source_date')
    for day, symbol in [(event['prior_date'], event['old_symbol']),
                        (event['effective_date'], event['new_symbol'])]:
        if (day not in facts.index or facts.loc[day, 'stock_ticker'] != symbol
                or facts.loc[day, 'source_status'] not in ('observed', 'listed_no_stock_observation')):
            raise ValueError('Rename must match both selected adjacent history sources')
    if (facts.loc[event['effective_date'], 'session_open_ns'] != event['effective_ns']
            or facts.loc[event['prior_date'], 'identity_span'] != facts.loc[event['effective_date'], 'identity_span']):
        raise ValueError('Rename history clock or continuity differs')


def compile_renames(unresolved, reviews, listings, history, calendar):
    """Caller verifies original listing and primary-publication capture bindings."""
    rows = {record_key(r): r for r in unresolved}
    if len(rows) != len(unresolved):
        raise ValueError('Unique original unresolved records required')
    sessions = sorted(calendar.sessions)
    consumed, transitions, events = set(), set(), []
    for review in reviews:
        ref = review['record']; key = record_key(ref)
        original = rows.get(key)
        if (key in consumed or original is None or key[:2] != ('alpaca', 'name_changes')
                or original['record_sha256'] != identity(original['record'])
                or ref['record_sha256'] != original['record_sha256']
                or review.get('conclusion') != 'unchanged_common_shares_ticker_change'
                or not review.get('evidence_identity')):
            raise ValueError('Exact reviewed original name-change record required')
        raw = original['record']; day = review['effective_date']; sid = review['security_id']
        if day not in sessions or sessions.index(day) == 0:
            raise ValueError('Adjacent captured exchange sessions required')
        prior = sessions[sessions.index(day)-1]
        before = listings.get((raw['old_symbol'], prior)); after = listings.get((raw['new_symbol'], day))
        if not before or not after:
            raise ValueError('Both original dated listings required')
        for row, symbol in [(before, raw['old_symbol']), (after, raw['new_symbol'])]:
            if (row.get('ticker') != symbol or row.get('composite_figi') != sid
                    or row.get('share_class_figi') != review['share_class_figi']
                    or not row.get('share_class_figi') or row.get('active') is not True
                    or row.get('primary_exchange') not in EXCHANGES or row.get('type') != 'CS'
                    or row.get('locale') != 'us' or row.get('market') != 'stocks'
                    or row.get('currency_name', '').lower() != 'usd'):
                raise ValueError('Rename cannot change the captured common-share identity')
        if (before.get('cik') and after.get('cik') and before['cik'] != after['cik']
                or review['prior_listing_sha256'] != identity(before)
                or review['effective_listing_sha256'] != identity(after)
                or (sid, day) in transitions):
            raise ValueError('Conflicting or changed rename evidence')
        effective = int(calendar.bounds(day)[0].tz_localize('UTC').value)
        event = dict(schema='v7-reviewed-common-share-rename-v1', event_id='rename:'+identity(review),
            security_id=sid, share_class_figi=review['share_class_figi'], old_symbol=raw['old_symbol'],
            new_symbol=raw['new_symbol'], prior_date=prior, effective_date=day,
            effective_ns=effective, available_ns=review['publication_available_ns'],
            share_quantity_factor=1, cash_delta=0, option_deliverables_admitted=False,
            review_identity=identity(review), evidence_identity=review['evidence_identity'], replaces=[ref])
        require_rename_history(event, history)
        consumed.add(key); transitions.add((sid, day)); events.append(event)
    return events, [row for row in unresolved if record_key(row) not in consumed]
