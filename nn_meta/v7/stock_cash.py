"""Authorized pre-tax dividend receivables for already admitted cash events."""
import math

import pandas as pd

from nn_meta.v7.action_inventory import iso_day, number
from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.storage import identity

POLICY_ID = 'pretax-funded-stock-cash-reconstruction-20260917'


def validate_policy(policy, proposal):
    if (policy.get('schema') != 'v7-stock-cash-ledger-admission-v1'
            or policy.get('status') != 'user_authorized' or policy.get('policy_id') != POLICY_ID
            or not policy.get('authorization') or not policy.get('proposal_sha256')
            or policy.get('scope_change') is not False or policy.get('research_ready') is not False
            or proposal.get('schema') != 'v7-stock-cash-ledger-reconstruction-proposal-v1'
            or policy.get('rules') != proposal.get('rules') or len(policy.get('rules', [])) != 6
            or policy.get('sources') != proposal.get('sources')
            or policy.get('eligible_existing_cash_events') != len(proposal['eligible_events'])):
        raise ValueError('Explicit finite authorized stock-cash policy required')
    return identity(policy)


def validate_cash_event(event, calendar=None, *, settlement_calendar=None):
    names=('event_id','compiled_event_id','security_id','symbol','policy_identity','source_identity')
    if (event.get('schema') != 'v7-stock-cash-entitlement-v1'
            or any(not isinstance(event.get(k),str) or not event[k] for k in names)
            or event.get('policy_id') != POLICY_ID or event.get('currency') != 'USD'
            or event.get('cash_units') != 'per_listed_share_or_unit'
            or not isinstance(event.get('cash_per_share'), str)
            or event.get('broker_posting_verified') is not False
            or event.get('withholding_fraction') != 0 or event.get('dividend_fee_per_share') != 0
            or any(type(event.get(k)) is not int for k in ('effective_ns','available_ns','release_ns'))
            or event['available_ns'] != event['effective_ns']
            or event['release_ns'] <= event['effective_ns']):
        raise ValueError('Authorized dated pre-tax cash entitlement required')
    amount=number(event.get('cash_per_share'))
    if not math.isfinite(float(amount)):
        raise ValueError('Finite cash distribution required')
    ex,record,pay=[iso_day(event[k]) for k in ('ex_date','record_date','pay_date')]
    effective_day=pd.Timestamp(event['effective_ns'],unit='ns',tz='UTC').tz_convert('America/New_York').date().isoformat()
    release_day=pd.Timestamp(event['release_ns'],unit='ns',tz='UTC').tz_convert('America/New_York').date().isoformat()
    if not ex==effective_day or not ex<=record<=pay<release_day:
        raise ValueError('Cash entitlement chronology differs')
    if calendar is not None:
        bounds=calendar.bounds(ex)
        calendar.bounds(pay)  # Payment may be a holiday, but must be covered.
        release=next((d for d in sorted(calendar.sessions) if d>pay),None)
        if (bounds is None or release is None
                or int(bounds[0].tz_localize('UTC').value)!=event['effective_ns']
                or int(calendar.bounds(release)[0].tz_localize('UTC').value)!=event['release_ns']):
            raise ValueError('Cash clocks differ from captured regular opens')
    if settlement_calendar is not None:
        coverage=settlement_calendar.document
        if not coverage['coverage_start']<=ex<=release_day<=coverage['coverage_end']:
            raise ValueError('Cash event exceeds captured settlement coverage')
    return event


def compile_cash_entitlements(events, candidates, calendar, policy, proposal):
    policy_identity=validate_policy(policy,proposal)
    original={record_key(r):r for r in candidates}
    admitted={e['action']['event_id']:e for e in events}
    eligible={r['event_id']:r for r in proposal['eligible_events']}
    if len(original)!=len(candidates) or len(admitted)!=len(events) or len(eligible)!=len(proposal['eligible_events']):
        raise ValueError('Unique source and approved event identities required')
    sessions=sorted(calendar.sessions);compiled=[];pending=[];clocks=set()
    for event_id,approved in eligible.items():
        source=admitted.get(event_id)
        if (source is None or source['category']!='cash' or source['symbol']!=approved['symbol']
                or source['security_id']!=approved['security_id']):
            raise ValueError('Cash event differs from finite authorized proposal')
        refs=source['replaces'];rows=[]
        for ref in refs:
            row=original.get(record_key(ref))
            if (row is None or row['category']!='cash' or ref['record_sha256']!=row['record_sha256']
                    or identity(row['record'])!=row['record_sha256']):
                raise ValueError('Cash event original source changed')
            rows.append(row)
        ex=iso_day(approved['ex_date']);record=iso_day(approved['record_date']);pay=iso_day(approved['pay_date'])
        if (not rows or {r['effective_date'] for r in rows}!={ex}
                or {r['record'].get('record_date') for r in rows}!={record}
                or {r['record'].get('pay_date' if r['provider']=='massive' else 'payable_date') for r in rows}!={pay}
                or any(r['record'].get(k) for r in rows for k in ('due_bill_on_date','due_bill_off_date'))
                or not ex<=record<=pay):
            raise ValueError('Reconciled cash dates or due-bill semantics differ')
        bounds=calendar.bounds(ex)
        release=next((d for d in sessions if d>pay),None)
        if bounds is None or release is None:
            pending.append(dict(event_id=event_id,reason='missing_captured_cash_release_calendar'));continue
        effective=int(bounds[0].tz_localize('UTC').value)
        if pd.Timestamp(source['action']['effective_at']).value!=effective:
            raise ValueError('Compiled price action clock differs')
        if (source['security_id'],effective) in clocks:
            raise ValueError('One combined cash entitlement per security clock required')
        clocks.add((source['security_id'],effective))
        event=dict(schema='v7-stock-cash-entitlement-v1',compiled_event_id=event_id,
            symbol=source['symbol'],security_id=source['security_id'],ex_date=ex,record_date=record,pay_date=pay,
            effective_ns=effective,available_ns=effective,
            release_ns=int(calendar.bounds(release)[0].tz_localize('UTC').value),
            cash_per_share=str(number(source['cash_amount'])),currency='USD',cash_units='per_listed_share_or_unit',
            withholding_fraction=0,dividend_fee_per_share=0,broker_posting_verified=False,
            policy_id=POLICY_ID,policy_identity=policy_identity,source_identity=identity(source),replaces=refs)
        event['event_id']='stock-cash:'+identity(event)
        validate_cash_event(event,calendar);compiled.append(event)
    excluded=[dict(event_id=e['action']['event_id'],symbol=e['symbol'],reason='outside_authorized_finite_cash_set')
              for e in events if e['category']=='cash' and e['action']['event_id'] not in eligible]
    return compiled,pending+excluded
