"""Finite extension of the existing model, gated by a separate user admission."""
import pandas as pd

from nn_meta.v7.action_inventory import iso_day, number
from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.stock_cash import POLICY_ID, validate_cash_event
from nn_meta.v7.storage import identity


def extension_candidates(actions, originals, base_events, calendar, proposal):
    """Return reviewable terms; this function does not emit admitted entitlements."""
    if (proposal.get('schema') != 'v7-remaining-stock-cash-extension-proposal-v1'
            or proposal.get('model_policy_id') != POLICY_ID
            or proposal.get('scope_change') is not False
            or proposal.get('research_ready') is not False
            or len(proposal.get('eligible_groups', [])) != proposal.get('finite_remaining_groups')):
        raise ValueError('Finite remaining cash scope required')
    by_record = {record_key(r): r for r in originals}
    if len(by_record) != len(originals) or any(identity(r['record']) != r['record_sha256'] for r in originals):
        raise ValueError('Unique original cash sources required')
    base_ids = {e['compiled_event_id'] for e in base_events}
    if len(base_ids) != len(base_events):
        raise ValueError('Unique existing authorized entitlements required')
    by_day = {}
    for e in actions:
        if e['category'] != 'cash':
            continue
        key = e['symbol'], e.get('effective_date', e['action']['effective_at'][:10])
        if key in by_day:
            raise ValueError('One compiled cash event per symbol/day required')
        by_day[key] = e
    ready, pending, seen = [], [], set()
    for group in proposal['eligible_groups']:
        key = group['symbol'], group['ex_date']
        if key in seen:
            raise ValueError('Duplicate finite cash group')
        seen.add(key)
        source = by_day.get(key)
        if source is None:
            pending.append(dict(symbol=key[0], ex_date=key[1], reason='cash_action_uncompiled'))
            continue
        event_id = source['action']['event_id']
        if event_id in base_ids:
            raise ValueError('Extension must not replace an existing authorized entitlement')
        refs = source['replaces']
        if sorted(refs, key=record_key) != sorted(group['replaces'], key=record_key):
            raise ValueError('Compiled event differs from the exact finite approved original group')
        rows = []
        for ref in refs:
            row = by_record.get(record_key(ref))
            if (not row or row['category'] != 'cash' or row['record_sha256'] != ref['record_sha256']
                    or row['subject_symbol'] != key[0] or row['effective_date'] != key[1]):
                raise ValueError('Compiled cash references differ from original provider rows')
            rows.append(row)
        record, pay = source.get('reviewed_record_date'), source.get('reviewed_pay_date')
        basis = 'compiled_primary_date_review'
        if record or pay:
            if (not record or not pay or source['admission_basis'] != 'reviewed_publication'
                    or not source.get('review_identity')):
                raise ValueError('Primary date correction must bind its admitted whole-event review')
        else:
            records = {r['record'].get('record_date') for r in rows}
            pays = {r['record'].get('pay_date' if r['provider'] == 'massive' else 'payable_date') for r in rows}
            if len(records) != 1 or len(pays) != 1 or None in records or None in pays:
                pending.append(dict(symbol=key[0], ex_date=key[1], reason='unresolved_record_or_pay_date'))
                continue
            record, pay, basis = records.pop(), pays.pop(), 'matching_provider_dates'
        ex, record, pay = iso_day(key[1]), iso_day(record), iso_day(pay)
        if (not ex or not record or not pay or not ex <= record <= pay
                or any(r['record'].get(k) for r in rows for k in ('due_bill_on_date', 'due_bill_off_date'))):
            pending.append(dict(symbol=key[0], ex_date=key[1], reason='requires_due_bill_or_date_review'))
            continue
        release = next((d for d in sorted(calendar.sessions) if d > pay), None)
        if (calendar.bounds(ex) is None or release is None
                or pd.Timestamp(source['action']['effective_at']).value !=
                    calendar.bounds(ex)[0].tz_localize('UTC').value):
            raise ValueError('Compiled cash clock or release horizon differs from captured calendar')
        ready.append(dict(compiled_event_id=event_id, symbol=source['symbol'], security_id=source['security_id'],
            cash_per_share=str(number(source['cash_amount'])), ex_date=ex, record_date=record,
            pay_date=pay, release_date=release, date_basis=basis,
            compiled_source_identity=identity(source), replaces=refs))
    return ready, pending


def compile_cash_extension(actions, originals, base_events, calendar, policy, proposal):
    if (policy.get('schema') != 'v7-remaining-stock-cash-extension-admission-v1'
            or policy.get('status') != 'user_authorized' or not policy.get('authorization')
            or policy.get('proposal_identity') != identity(proposal)
            or policy.get('model_policy_id') != POLICY_ID):
        raise ValueError('Explicit user authorization of the exact finite cash extension required')
    ready, pending = extension_candidates(actions, originals, base_events, calendar, proposal)
    result = list(base_events)
    for row in ready:
        effective = int(calendar.bounds(row['ex_date'])[0].tz_localize('UTC').value)
        event = dict(schema='v7-stock-cash-entitlement-v1', compiled_event_id=row['compiled_event_id'],
            symbol=row['symbol'], security_id=row['security_id'], ex_date=row['ex_date'],
            record_date=row['record_date'], pay_date=row['pay_date'],
            effective_ns=effective, available_ns=effective,
            release_ns=int(calendar.bounds(row['release_date'])[0].tz_localize('UTC').value),
            cash_per_share=row['cash_per_share'], currency='USD', cash_units='per_listed_share_or_unit',
            withholding_fraction=0, dividend_fee_per_share=0, broker_posting_verified=False,
            policy_id=POLICY_ID, policy_identity=identity(policy),
            source_identity=row['compiled_source_identity'], replaces=row['replaces'], date_basis=row['date_basis'])
        event['event_id'] = 'stock-cash:' + identity(event)
        validate_cash_event(event, calendar)
        result.append(event)
    clocks = [(e['security_id'], e['effective_ns']) for e in result]
    if len(set(clocks)) != len(clocks):
        raise ValueError('One combined entitlement per security/ex-open required')
    return result, pending
