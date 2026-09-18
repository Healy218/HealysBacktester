"""Finite primary-source dividend terms for the authorized reconstruction model.

Current issuer/depositary histories establish terms, not historical publication.
Every review keeps its entire original record group and an explicit price basis.
"""
from collections import defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal
import math

import pandas as pd

from nn_meta.v7.action_inventory import number, iso_day
from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.causal_prices import PriceAction, cash_distribution_action
from nn_meta.v7.storage import identity
from nn_meta.v7.stock_cash import POLICY_ID, validate_cash_event

BASIS = 'primary_terms_effective_session_reconstruction'


@dataclass(frozen=True)
class ReviewedDividendAction(PriceAction):
    admission_policy_identity: str
    review_identity: str
    admission_basis: str = BASIS
    publication_verified: bool = False
    publication_available_at: None = None

    def __post_init__(self):
        super().__post_init__()
        if (self.admission_basis != BASIS or not self.admission_policy_identity
                or not self.review_identity or self.available_at != self.effective_at
                or self.publication_verified is not False or self.publication_available_at is not None):
            raise ValueError('Explicit primary-terms reconstruction required')


def validate_resolution_policy(policy):
    expected = dict(schema='v7-dividend-resolution-policy-v1', status='user_authorized',
        scope_change=False, currency='USD', model_policy_id=POLICY_ID,
        publication_verified=False, require_primary_terms=True,
        withholdings_and_fees_modeled=False, preserve_original_records=True)
    if any(policy.get(k) != v or type(policy.get(k)) != type(v) for k,v in expected.items()) or not policy.get('authorization'):
        raise ValueError('Authorized finite dividend resolution policy required')
    return identity(policy)


def compile_dividend_resolutions(originals, reviews, history, calendar, policy, proposal):
    policy_id=validate_resolution_policy(policy)
    if identity(proposal) != policy.get('proposal_identity'):
        raise ValueError('Exact original finite cash proposal required')
    approved = {record_key(r): r['record_sha256']
        for g in proposal['eligible_groups'] for r in g['replaces']}
    by_key={record_key(r):r for r in originals}
    if len(by_key)!=len(originals) or any(identity(r['record'])!=r['record_sha256'] for r in originals):
        raise ValueError('Unique unchanged provider records required')
    groups=defaultdict(set)
    for r in originals:
        if r['category']=='cash':groups[r['subject_symbol'],r['effective_date']].add(record_key(r))
    selected=history[history.stock_ticker.notna()]
    if selected.duplicated(['stock_ticker','source_date']).any():raise ValueError('Unique selected stock history required')
    facts=selected.set_index(['stock_ticker','source_date'])
    sessions=sorted(calendar.sessions)
    actions=[];entitlements=[];consumed=set();clocks=set()
    for review in reviews:
        if (review.get('schema')!='v7-primary-dividend-resolution-v1' or not review.get('evidence_identity')
                or not review.get('rationale') or review.get('currency')!='USD'
                or review.get('cash_units')!='per_listed_share_or_unit'
                or review.get('publication_verified') is not False):
            raise ValueError('Exact retained primary dividend terms required')
        refs=review['replaces'];keys={record_key(r) for r in refs}
        if not keys or len(keys)!=len(refs) or consumed&keys:raise ValueError('Unique whole original groups required')
        evidence=review.get('evidence', [])
        if not evidence or identity(evidence)!=review['evidence_identity']:
            raise ValueError('Primary evidence identity differs')
        rows=[]
        for ref in refs:
            row=by_key.get(record_key(ref))
            if (not row or ref['record_sha256']!=row['record_sha256'] or row['category']!='cash'
                    or approved.get(record_key(ref)) != row['record_sha256']):
                raise ValueError('Dividend source reference differs')
            if any(row['record'].get(k) for k in ('due_bill_on_date','due_bill_off_date')):
                raise ValueError('Due-bill cash needs separate entitlement treatment')
            if row['subject_symbol']!=review['symbol']:raise ValueError('Cross-symbol dividend needs identity routing first')
            rows.append(row)
        for row in rows:
            if not groups[row['subject_symbol'],row['effective_date']]<=keys:
                raise ValueError('Review must replace each entire original cash group')
        symbol=review['symbol'];ex=iso_day(review['ex_date']);sid=review['security_id']
        if any(r['effective_date']==ex and symbol in r['scoped_symbols'] and r['category']!='cash'
               for r in originals):
            raise ValueError('Mixed corporate actions need joint review')
        if (sid, ex) in clocks:raise ValueError('One whole reviewed event per security session required')
        clocks.add((sid, ex))
        if ex not in sessions or sessions.index(ex)==0:raise ValueError('Captured previous session required')
        prior=sessions[sessions.index(ex)-1]
        if any(k not in facts.index for k in [(symbol,prior),(symbol,ex)]):raise ValueError('Adjacent selected identity required')
        prev,now=facts.loc[symbol,prior],facts.loc[symbol,ex]
        if (prev.security_id!=sid or now.security_id!=sid or pd.isna(prev.identity_span)
                or prev.identity_span!=now.identity_span):raise ValueError('Dividend cannot bridge unresolved security identity')
        close=calendar.bounds(prior)[1].tz_localize('UTC');effective=calendar.bounds(ex)[0].tz_localize('UTC')
        if (prev.available_ns!=close.value or now.session_open_ns!=effective.value
                or pd.isna(prev.observed_minutes) or prev.observed_minutes<=0):raise ValueError('Observed preceding close required')
        payments=review['payments']
        if not payments or len({p['name'] for p in payments})!=len(payments):raise ValueError('Named unique payments required')
        total=Decimal(0)
        for p in payments:
            amount=number(p['cash_per_share']);record=iso_day(p['record_date']);pay=iso_day(p['pay_date'])
            if amount<=0 or not math.isfinite(float(amount)) or not ex<=record<=pay:
                raise ValueError('Positive dated cash components required')
            if p.get('terms_evidence_identity') not in {identity(e) for e in evidence}:
                raise ValueError('Each component must bind primary terms')
            total+=amount
        if total!=number(review['cash_per_share']):raise ValueError('Payments must reconcile to total cash')
        digest=identity(review);event_id='dividend-reviewed:'+digest
        action=cash_distribution_action(cash_per_share=float(total),prior_raw_close=float(prev.raw_close),
            prior_close_at=close,event_id=event_id,effective_at=effective,available_at=effective,source_identity=digest)
        action=ReviewedDividendAction(**asdict(action),admission_policy_identity=policy_id,review_identity=digest)
        serialized=asdict(action)
        for k in ('effective_at','available_at'):serialized[k]=serialized[k].isoformat()
        event=dict(symbol=symbol,security_id=sid,effective_date=ex,category='cash',cash_amount=str(total),
            cash_units='USD_per_listed_share_or_unit',admission_basis=BASIS,admission_policy_identity=policy_id,
            review_identity=digest,publication_verified=False,publication_available_at=None,replaces=refs,
            action=serialized,full_security_admitted=False,prior_source_date=prior,prior_raw_close=float(prev.raw_close),
            reviewed_payments=payments,held_position_treatment='authorized_pretax_cash_components')
        actions.append(event)
        # Separate leaf events preserve different payment clocks; the whole price event is applied once.
        for i,p in enumerate(payments):
            release=next((d for d in sessions if d>p['pay_date']),None)
            if release is None:raise ValueError('Missing captured payment release horizon')
            cash=dict(schema='v7-stock-cash-entitlement-v1',compiled_event_id=event_id,
                symbol=symbol,security_id=sid,ex_date=ex,record_date=p['record_date'],pay_date=p['pay_date'],
                effective_ns=int(effective.value),available_ns=int(effective.value),
                release_ns=int(calendar.bounds(release)[0].tz_localize('UTC').value),
                cash_per_share=str(number(p['cash_per_share'])),currency='USD',cash_units='per_listed_share_or_unit',
                withholding_fraction=0,dividend_fee_per_share=0,broker_posting_verified=False,
                policy_id=POLICY_ID,policy_identity=policy_id,source_identity=identity(event),replaces=refs,
                date_basis='retained_primary_dividend_terms',dividend_component_index=i,
                dividend_component_count=len(payments),dividend_component_name=p['name'],
                date_review_identity=digest,date_evidence_identity=p['terms_evidence_identity'])
            cash['event_id']='stock-cash:'+identity(cash);validate_cash_event(cash,calendar);entitlements.append(cash)
        consumed.update(keys)
    return actions,entitlements,[r for r in originals if record_key(r) not in consumed]
