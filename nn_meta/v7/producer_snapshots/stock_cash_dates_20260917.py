"""Primary date corrections for already compiled cash price actions."""
import pandas as pd

from nn_meta.v7.action_inventory import iso_day, number
from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.ordinary_actions import price_action
from nn_meta.v7.stock_cash import POLICY_ID, validate_cash_event
from nn_meta.v7.storage import identity


def compile_date_reviewed_cash(actions, originals, base_events, calendar, policy, proposal, reviews):
    """Preserve chart inputs and existing entitlements; correct only reviewed dates."""
    if (policy.get('schema') != 'v7-remaining-stock-cash-extension-admission-v1'
            or policy.get('status') != 'user_authorized' or not policy.get('authorization')
            or policy.get('proposal_identity') != identity(proposal)
            or policy.get('model_policy_id') != POLICY_ID):
        raise ValueError('Exact authorized finite cash extension required')
    scope = {(r['symbol'], r['ex_date']): r for r in proposal['eligible_groups']}
    if len(scope) != len(proposal['eligible_groups']):
        raise ValueError('Unique finite scope required')
    by_id = {e['action']['event_id']: e for e in actions}
    by_record = {record_key(r): r for r in originals}
    if len(by_id) != len(actions) or len(by_record) != len(originals):
        raise ValueError('Unique compiled and original source identities required')
    consumed = {e['compiled_event_id'] for e in base_events}
    if len(consumed) != len(base_events):
        raise ValueError('Duplicate existing cash entitlement')
    result = list(base_events)
    for review in reviews:
        event_id = review['compiled_event_id']
        source = by_id.get(event_id)
        key = review['symbol'], review['ex_date']
        if (review.get('schema') != 'v7-primary-cash-date-review-v1'
                or not review.get('evidence_identity') or not review.get('rationale')
                or review.get('conclusion') != 'ordinary_cash_dates_resolved'
                or review.get('publication_time_used_for_chart') is not False
                or not source or source['category'] != 'cash' or key not in scope
                or event_id in consumed or identity(source) != review['compiled_source_identity']
                or source['security_id'] != review['security_id'] or source['symbol'] != key[0]
                or number(source['cash_amount']) != number(review['cash_per_share'])):
            raise ValueError('Exact source-bound ordinary cash date review required')
        refs = sorted(source['replaces'], key=record_key)
        if refs != sorted(scope[key]['replaces'], key=record_key) or refs != sorted(review['replaces'], key=record_key):
            raise ValueError('Date review must retain the entire approved original record group')
        for ref in refs:
            row = by_record.get(record_key(ref))
            if (not row or row['category'] != 'cash' or row['effective_date'] != key[1]
                    or row['subject_symbol'] != key[0] or row['record_sha256'] != ref['record_sha256']
                    or identity(row['record']) != row['record_sha256']
                    or any(row['record'].get(k) for k in ('due_bill_on_date', 'due_bill_off_date'))):
                raise ValueError('Changed original, different ex-date, or unresolved due-bill semantics')
        ex, record, pay = [iso_day(review[k]) for k in ('ex_date', 'record_date', 'pay_date')]
        if not ex or not record or not pay or not ex <= record <= pay:
            raise ValueError('Nonstandard ex/record/pay ordering requires separate treatment')
        action = price_action(source)
        bounds = calendar.bounds(ex)
        release = next((d for d in sorted(calendar.sessions) if d > pay), None)
        if bounds is None or release is None or action.effective_at.value != bounds[0].tz_localize('UTC').value:
            raise ValueError('Original chart clock or cash release calendar differs')
        effective = int(action.effective_at.value)
        event = dict(schema='v7-stock-cash-entitlement-v1', compiled_event_id=event_id,
            symbol=source['symbol'], security_id=source['security_id'], ex_date=ex,
            record_date=record, pay_date=pay, effective_ns=effective, available_ns=effective,
            release_ns=int(calendar.bounds(release)[0].tz_localize('UTC').value),
            cash_per_share=str(number(source['cash_amount'])), currency='USD', cash_units='per_listed_share_or_unit',
            withholding_fraction=0, dividend_fee_per_share=0, broker_posting_verified=False,
            policy_id=POLICY_ID, policy_identity=identity(policy), source_identity=identity(source),
            replaces=source['replaces'], date_basis='retained_primary_date_review',
            date_review_identity=identity(review), date_evidence_identity=review['evidence_identity'])
        event['event_id'] = 'stock-cash:' + identity(event)
        validate_cash_event(event, calendar)
        result.append(event); consumed.add(event_id)
    clocks = [(e['security_id'], e['effective_ns']) for e in result]
    if len(set(clocks)) != len(clocks):
        raise ValueError('Duplicate cash entitlement at one security/ex-open')
    return result
