"""Compile reviewed whole cash events; never infer a complete action history."""
from collections import defaultdict
from dataclasses import asdict

import pandas as pd

from nn_meta.v7.action_inventory import iso_day, number
from nn_meta.v7.causal_prices import cash_distribution_action
from nn_meta.v7.storage import identity


def record_key(row):
    return row['provider'], row['kind'], row['action_id']


def compile_cash_actions(candidates, reviews, stock, calendar):
    """Return only explicit replacements and all still-unconsumed records.

    Reviews are upstream evidence, not boolean waivers. Each names exact source
    records/hashes and one total USD/common-share cash amount. The caller must
    verify their retained source receipts. Event compilation proves neither
    complete no-event intervals nor full-security continuity outside these two
    adjacent eligible dates. Unknown actions are never converted to factor one.
    """
    candidates, reviews = list(candidates), list(reviews)
    by_key, by_day = {}, defaultdict(list)
    for row in candidates:
        key = record_key(row)
        if key in by_key or row['record_sha256'] != identity(row['record']):
            raise ValueError('Duplicate or changed original action record')
        by_key[key] = row
        if row['effective_date']:
            for symbol in row['scoped_symbols']:
                by_day[symbol, row['effective_date']].append(row)
    needed = {'stock_ticker', 'source_date', 'security_id', 'raw_close',
              'observed_minutes', 'available_ns'}
    if not needed.issubset(stock) or stock.duplicated(['stock_ticker', 'source_date']).any():
        raise ValueError('Unique exact-date eligible stock facts required')
    facts = stock.set_index(['stock_ticker', 'source_date'])
    sessions = sorted(calendar.sessions)
    positions = {day:i for i,day in enumerate(sessions)}
    consumed, event_ids, events, clocks = set(), set(), [], set()
    for review in reviews:
        symbol, day = review['symbol'], iso_day(review['effective_date'])
        identifier, security = review['event_id'], review['security_id']
        if (not isinstance(identifier, str) or not identifier or identifier in event_ids
                or not isinstance(security, str) or not security
                or not isinstance(review.get('evidence_identity'), str) or not review['evidence_identity']
                or review.get('currency') != 'USD' or review.get('cash_units') != 'per_common_share'):
            raise ValueError('Unique identified reviewed USD common-share event required')
        event_ids.add(identifier)
        references = review['replaces']
        keys = [record_key(r) for r in references]
        group = by_day.get((symbol, day), [])
        if (not keys or len(set(keys)) != len(keys) or consumed.intersection(keys)
                or set(keys) != {record_key(r) for r in group}):
            raise ValueError('Cash review must replace the entire event group exactly once')
        if any(r['category'] != 'cash' or r['subject_symbol'] != symbol for r in group):
            raise ValueError('Mixed or complex simultaneous actions need a combined review')
        for reference in references:
            if reference['record_sha256'] != by_key[record_key(reference)]['record_sha256']:
                raise ValueError('Reviewed provider record changed')
        if day not in positions or positions[day] == 0:
            raise ValueError('Captured preceding exchange session required')
        prior_day = sessions[positions[day]-1]
        if (symbol,day) not in facts.index or (symbol,prior_day) not in facts.index:
            raise ValueError('Both adjacent eligible security dates required')
        prior, current = facts.loc[(symbol,prior_day)], facts.loc[(symbol,day)]
        if prior.security_id != security or current.security_id != security:
            raise ValueError('Adjacent security identities differ from review')
        close = calendar.bounds(prior_day)[1].tz_localize('UTC')
        effective = calendar.bounds(day)[0].tz_localize('UTC')
        if (pd.isna(prior.observed_minutes) or prior.observed_minutes <= 0
                or pd.isna(prior.available_ns) or prior.available_ns != close.value):
            raise ValueError('Observed prior-session close and exact availability required')
        if (security, effective.value) in clocks:
            raise ValueError('One combined action per security and effective clock required')
        clocks.add((security,effective.value))
        cash = number(review['cash_amount'])
        action = cash_distribution_action(cash_per_share=float(cash), prior_raw_close=float(prior.raw_close),
            prior_close_at=close, event_id=identifier, effective_at=effective,
            available_at=pd.Timestamp(review['publication_available_at']),
            source_identity=identity(review))
        serialized = asdict(action)
        for field in ('effective_at','available_at'):
            serialized[field] = serialized[field].isoformat()
        events.append(dict(symbol=symbol,security_id=security,cash_amount=str(cash),
            prior_source_date=prior_day,prior_raw_close=float(prior.raw_close),
            prior_close_at=close.isoformat(),review_identity=identity(review),
            replaces=references,action=serialized,full_security_admitted=False))
        consumed.update(keys)
    unresolved = [row for row in candidates if record_key(row) not in consumed]
    return events, unresolved
