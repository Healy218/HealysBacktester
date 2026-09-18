"""Incremental, primary-reviewed cash corrections retaining every original row."""
from decimal import Decimal

import pandas as pd

from nn_meta.v7.action_inventory import candidate, iso_day, number
from nn_meta.v7.cash_actions import compile_cash_actions


def compile_reviewed_cash(candidates, reviews, history, calendar):
    candidates, reviews = list(candidates), list(reviews)
    for row in candidates:
        rebuilt = candidate(row['provider'], row['kind'], row['record'],
            scoped_symbols=set(row['scoped_symbols']), start=calendar.start, end=calendar.end,
            source=row['source'])
        if {k: row[k] for k in rebuilt} != rebuilt:
            raise ValueError('Changed normalized cash source')
    required = {'stock_ticker', 'source_date', 'security_id', 'identity_span'}
    selected = history[history.stock_ticker.notna()]
    if (not required.issubset(history)
            or selected.duplicated(['stock_ticker', 'source_date']).any()):
        raise ValueError('Unique selected identity history required')
    facts = selected.set_index(['stock_ticker', 'source_date'])
    sessions = sorted(calendar.sessions)
    for review in reviews:
        day = iso_day(review['effective_date'])
        if (review.get('schema') != 'v7-primary-common-share-cash-review-v1'
                or review.get('other_security_entitlement') is not False
                or review.get('currency') != 'USD' or review.get('cash_units') != 'per_common_share'
                or not review.get('rationale')):
            raise ValueError('Explicit primary common-share cash review required')
        components = review.get('components', [])
        if (not components or any(not c.get('name') for c in components)
                or len({c['name'] for c in components}) != len(components)
                or sum((number(c['cash_amount']) for c in components), Decimal(0))
                    != number(review['cash_amount'])):
            raise ValueError('Primary named cash components must reconcile exactly')
        record, pay = iso_day(review['record_date']), iso_day(review['pay_date'])
        if not record or not pay or not day <= record <= pay:
            raise ValueError('Ordinary ex/record/pay order required; due bills need separate treatment')
        published = pd.Timestamp(review['publication_available_at'])
        if (pd.isna(published) or published.tz is None or day not in sessions
                or published > calendar.bounds(day)[0].tz_localize('UTC')):
            raise ValueError('Reviewed publication must precede the effective open')
        index = sessions.index(day)
        prior_key, current_key = (review['symbol'], sessions[index-1]), (review['symbol'], day)
        if index == 0 or prior_key not in facts.index or current_key not in facts.index:
            raise ValueError('Adjacent selected identity dates required')
        prior, current = facts.loc[prior_key], facts.loc[current_key]
        if (pd.isna(prior.identity_span) or pd.isna(current.identity_span)
                or prior.identity_span != current.identity_span):
            raise ValueError('Cash review cannot bridge a share-class lifecycle change')
    events, pending = compile_cash_actions(candidates, reviews, selected, calendar)
    for event, review in zip(events, reviews, strict=True):
        event.update(category='cash', admission_basis='reviewed_publication',
            effective_date=review['effective_date'], publication_verified=True,
            publication_available_at=review['publication_available_at'],
            cash_units='USD_per_listed_share_or_unit',
            reviewed_record_date=review['record_date'], reviewed_pay_date=review['pay_date'],
            reviewed_components=review['components'],
            held_position_treatment='requires_separate_authorized_entitlement')
    return events, pending
