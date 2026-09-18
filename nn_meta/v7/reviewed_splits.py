"""Finite primary-reviewed same-share splits reported as stock dividends.

The provider category is never remapped globally: warrants, other securities,
combined actions and unreviewed events remain unresolved.
"""
from collections import defaultdict
from dataclasses import asdict

import pandas as pd

from nn_meta.v7.action_inventory import candidate,iso_day,number
from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.causal_prices import split_action
from nn_meta.v7.storage import identity


def compile_reviewed_splits(candidates,reviews,history,calendar):
    candidates=list(candidates)
    by_key={record_key(r):r for r in candidates};by_day=defaultdict(list)
    if len(by_key)!=len(candidates) or any(identity(r['record'])!=r['record_sha256'] for r in candidates):
        raise ValueError('Unique unchanged original split records required')
    for r in candidates:
        rebuilt=candidate(r['provider'],r['kind'],r['record'],scoped_symbols=set(r['scoped_symbols']),
            start='0001-01-01',end='9999-12-31',source=r['source'])
        if rebuilt is None or any(r.get(k)!=v for k,v in rebuilt.items()):
            raise ValueError('Changed normalized split record')
        if r['effective_date']:
            for symbol in r['scoped_symbols']:by_day[symbol,r['effective_date']].append(r)
    selected=history[history.stock_ticker.notna()]
    if selected.duplicated(['stock_ticker','source_date']).any():
        raise ValueError('Unique selected dated security history required')
    facts=selected.set_index(['stock_ticker','source_date']);sessions=sorted(calendar.sessions)
    consumed=set();events=[];clocks=set()
    for review in reviews:
        symbol=review['symbol'];day=iso_day(review['effective_date']);sid=review['security_id']
        ratio=number(review['new_shares_per_old_share'])
        if (review.get('schema')!='v7-reviewed-same-share-split-v1'
                or review.get('conclusion')!='same_share_class_forward_split'
                or not review.get('evidence_identity') or not sid
                or ratio<=1 or ratio!=ratio.to_integral_value()
                or review.get('other_security_entitlement') is not False
                or review.get('cash_entitlement')!=0):
            raise ValueError('Reviewed integer same-share forward split required')
        refs=review['replaces'];keys=[record_key(r) for r in refs];group=by_day[symbol,day]
        if (len(keys)!=2 or len(set(keys))!=2 or consumed.intersection(keys)
                or set(keys)!={record_key(r) for r in group}
                or {(r['provider'],r['kind']) for r in group}!={('massive','splits'),('alpaca','forward_splits')}):
            raise ValueError('Review must replace the complete two-provider split group')
        for ref in refs:
            r=by_key[record_key(ref)]
            expected_issues=['not_a_declared_simple_split'] if r['provider']=='massive' else []
            if (r['category']!='split' or r['subject_symbol']!=symbol
                    or r['record_sha256']!=ref['record_sha256'] or number(r['term'])!=ratio
                    or r['term_issues']!=expected_issues
                    or (r['provider']=='massive' and r['record'].get('adjustment_type')!='stock_dividend')):
                raise ValueError('Reviewed exact terms differ from original split records')
        if day not in sessions or sessions.index(day)==0:
            raise ValueError('Captured adjacent exchange sessions required')
        prior=sessions[sessions.index(day)-1]
        if (symbol,day) not in facts.index or (symbol,prior) not in facts.index:
            raise ValueError('Both selected adjacent security dates required')
        before,after=facts.loc[(symbol,prior)],facts.loc[(symbol,day)]
        if (before.security_id!=sid or after.security_id!=sid
                or pd.isna(before.identity_span) or before.identity_span!=after.identity_span):
            raise ValueError('Split cannot coalesce different or unknown security identities')
        effective=calendar.bounds(day)[0].tz_localize('UTC')
        available=pd.Timestamp(review['publication_available_at'])
        if (pd.isna(available) or available.tzinfo is None or available>effective
                or after.session_open_ns!=effective.value or (sid,effective.value) in clocks):
            raise ValueError('Exact split clock and prior publication required')
        action=split_action(old_shares=1.,new_shares=float(ratio),effective_at=effective,
            available_at=available,event_id='reviewed-split:'+identity(review),source_identity=identity(review))
        value=asdict(action)
        for k in ('effective_at','available_at'):value[k]=value[k].isoformat()
        events.append(dict(symbol=symbol,security_id=sid,effective_date=day,category='split',
            new_shares_per_old_share=str(ratio),cash_amount=None,cash_units=None,
            admission_basis='reviewed_publication',publication_available_at=available.isoformat(),
            publication_verified=True,review_identity=identity(review),evidence_identity=review['evidence_identity'],
            prior_source_date=prior,replaces=refs,action=value,full_security_admitted=False,
            held_position_treatment='requires_entitlement_and_deliverable_evidence'))
        consumed.update(keys);clocks.add((sid,effective.value))
    return events,[r for r in candidates if record_key(r) not in consumed]
