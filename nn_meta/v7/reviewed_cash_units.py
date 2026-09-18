"""Matching cash reconstruction after an exact common-share unit review."""
from collections import defaultdict
from dataclasses import asdict

import pandas as pd

from nn_meta.v7.action_inventory import candidate, number
from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.causal_prices import cash_distribution_action
from nn_meta.v7.ordinary_actions import BASIS, ReconstructionAction, serialized_action, validate_policy
from nn_meta.v7.storage import identity


def compile_unit_reviewed_cash(candidates, reviews, witnesses, history, calendar, policy):
    """Resolve units only; never reconcile unequal rates, currencies or dates.

    An earlier primary notice defines USD/common-share units. Selected identity
    continuity links that same share class to the later event. Event amounts and
    availability remain explicitly assumed from the matching provider records.
    """
    policy_id = validate_policy(policy)
    groups = defaultdict(list)
    for row in candidates:
        rebuilt = candidate(row['provider'], row['kind'], row['record'],
            scoped_symbols=set(row['scoped_symbols']), start=calendar.start, end=calendar.end,
            source=row['source'])
        if {k: row[k] for k in rebuilt} != rebuilt:
            raise ValueError('Changed original or normalized unit-review record')
        for symbol in row['scoped_symbols']:
            groups[symbol, row['effective_date']].append(row)
    selected = history[history.stock_ticker.notna()]
    if selected.duplicated(['stock_ticker', 'source_date']).any():
        raise ValueError('Unique dated selected identity required')
    facts = selected.set_index(['stock_ticker', 'source_date'])
    sessions = sorted(calendar.sessions)
    events, consumed = [], set()
    for review in reviews:
        if review.get('schema') != 'v7-finite-matching-cash-unit-review-v1':
            raise ValueError('Finite exact cash unit review required')
        symbol, day = review['symbol'], review['effective_date']
        rows = groups[symbol, day]
        refs = review['replaces']
        if (len(rows) != 2 or {r['provider'] for r in rows} != {'massive', 'alpaca'}
                or any(r['category'] != 'cash' or r['subject_symbol'] != symbol for r in rows)
                or len(refs) != 2 or {record_key(r) for r in refs} != {record_key(r) for r in rows}
                or consumed.intersection(record_key(r) for r in rows)):
            raise ValueError('Unique exact two-provider whole cash group required')
        for row in rows:
            ref = next(r for r in refs if record_key(r) == record_key(row))
            if (ref['record_sha256'] != row['record_sha256']
                    or set(row['term_issues']) - {'foreign_or_unspecified_cash_units'}):
                raise ValueError('Only the foreign unit flag may be resolved by this review')
        massive = next(r for r in rows if r['provider'] == 'massive')
        amount = number(review['cash_amount'])
        if massive['record'].get('currency') != 'USD' or any(number(r['term']) != amount for r in rows):
            raise ValueError('Matching original USD amounts required; gross/net differences stay unresolved')
        witness = witnesses.get(review['unit_witness_event_id'])
        if (not witness or identity(witness) != review['unit_witness_review_identity']
                or witness['schema'] != 'v7-primary-common-share-cash-review-v1'
                or witness['currency'] != 'USD' or witness['cash_units'] != 'per_common_share'
                or witness['symbol'] != symbol or witness['security_id'] != review['security_id']
                or witness['effective_date'] > day):
            raise ValueError('Earlier primary USD/common-share witness required')
        if day not in sessions or sessions.index(day) == 0:
            raise ValueError('Prior captured session required')
        prior_day = sessions[sessions.index(day)-1]
        keys = [(symbol, d) for d in (witness['effective_date'], prior_day, day)]
        if any(k not in facts.index for k in keys):
            raise ValueError('Unit witness and adjacent selected dates required')
        witness_day, prior, current = [facts.loc[k] for k in keys]
        if (any(r.security_id != review['security_id'] or pd.isna(r.identity_span) for r in
                (witness_day, prior, current))
                or len({r.identity_span for r in (witness_day, prior, current)}) != 1):
            raise ValueError('Unit witness cannot cross a share-class identity discontinuity')
        close, effective = calendar.bounds(prior_day)[1].tz_localize('UTC'), calendar.bounds(day)[0].tz_localize('UTC')
        if (prior.available_ns != close.value or current.session_open_ns != effective.value
                or pd.isna(prior.observed_minutes) or prior.observed_minutes <= 0):
            raise ValueError('Observed prior close and exact calendar clocks required')
        evidence = dict(review=review, policy_identity=policy_id, identity_span=current.identity_span,
            prior_source_date=prior_day, prior_raw_close=float(prior.raw_close))
        digest = identity(evidence)
        action = cash_distribution_action(cash_per_share=float(amount), prior_raw_close=float(prior.raw_close),
            prior_close_at=close, event_id='unit-reviewed-'+digest, effective_at=effective,
            available_at=effective, source_identity=digest)
        action = ReconstructionAction(**asdict(action), admission_policy_identity=policy_id)
        events.append(dict(symbol=symbol, security_id=review['security_id'], effective_date=day,
            category='cash', cash_amount=str(amount), cash_units='USD_per_listed_share_or_unit',
            admission_basis=BASIS, admission_policy_identity=policy_id, evidence=evidence,
            publication_verified=False, publication_available_at=None, replaces=refs,
            action=serialized_action(action), full_security_admitted=False,
            held_position_treatment='requires_separate_authorized_entitlement'))
        consumed.update(record_key(r) for r in rows)
    return events, [r for r in candidates if record_key(r) not in consumed]
