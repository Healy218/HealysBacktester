"""Nominal cash-payment date reviews, independent of distribution tax label.

The historical compiler's 'ordinary' conclusion means standard ex/record/pay
ordering. Its validation is retained; the public review preserves special cash
and qualified nominal payment wording without asserting actual broker posting.
"""
from nn_meta.v7.stock_cash_dates import compile_date_reviewed_cash
from nn_meta.v7.dividend_components import validate_components
from nn_meta.v7.storage import identity


def compile_remaining_dates(actions, originals, base_events, calendar, policy, proposal, reviews):
    validate_components(actions, base_events, calendar)
    legacy = [e for e in base_events if 'dividend_component_index' not in e]
    occupied = {e['compiled_event_id'] for e in base_events}
    normalized = []
    for r in reviews:
        if (r.get('conclusion') != 'cash_distribution_dates_resolved'
                or r.get('distribution_kind') not in ('regular_cash', 'special_cash')
                or r.get('pay_date_qualifier') not in ('stated_date', 'on_or_about', 'on_or_after')
                or r.get('payment_model') != 'nominal_date_broker_posting_unverified'
                or r['compiled_event_id'] in occupied
                or r.get('option_treatment_resolved') is not False):
            raise ValueError('Explicit nominal cash terms and separate option treatment required')
        if r['distribution_kind'] == 'special_cash' and not r.get('option_notice_evidence_identity'):
            raise ValueError('Special cash must retain separate option notice evidence')
        normalized.append(dict(r, conclusion='ordinary_cash_dates_resolved'))
    added = compile_date_reviewed_cash(actions, originals, legacy, calendar, policy,
        proposal, normalized)[len(legacy):]
    for e, r in zip(added, reviews, strict=True):
        e['date_review_identity'] = identity(r)
        for k in ('distribution_kind', 'pay_date_qualifier', 'payment_model', 'option_treatment_resolved'):
            e[k] = r[k]
        if 'option_notice_evidence_identity' in r:
            e['option_notice_evidence_identity'] = r['option_notice_evidence_identity']
        e.pop('event_id')
        e['event_id'] = 'stock-cash:' + identity(e)
    result = list(base_events) + added
    validate_components(actions, result, calendar)
    return result
