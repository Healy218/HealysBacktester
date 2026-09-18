"""Finite same-unit provider rounding reconciliation, without a primary-amount claim."""
from decimal import Decimal, ROUND_HALF_UP
from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.storage import identity
from nn_meta.v7.dividend_resolution import compile_dividend_resolutions
from nn_meta.v7.ordinary_actions import BASIS,ReconstructionAction,serialized_action


def validate_provider_precision(originals,review,policy):
    if (policy.get('schema')!='v7-finite-dividend-provider-precision-v1'
            or policy.get('status')!='authorized_implementation' or not policy.get('authorization')
            or policy.get('primary_amount_verified') is not False
            or policy.get('withholdings_and_fees_modeled') is not False
            or policy.get('scope_change') is not False
            or policy.get('replaces')!=review['replaces']
            or (review['symbol'],review['ex_date'])!=('ETHE','2026-09-03')
            or review.get('amount_basis')!='paired_provider_decimal_precision'
            or review.get('primary_amount_verified') is not False
            or review.get('primary_unit_evidence_identity') not in {identity(e) for e in review['evidence']}
            or len(review['payments'])!=1):
        raise ValueError('Finite source-bound provider precision policy required')
    by_key={record_key(r):r for r in originals}
    rows=[by_key[record_key(r)] for r in review['replaces']]
    whole={record_key(r) for r in originals if r['category']=='cash' and
           r['subject_symbol']==review['symbol'] and r['effective_date']==review['ex_date']}
    if len(rows)!=2 or {r['provider'] for r in rows}!={'alpaca','massive'} or whole!={record_key(r) for r in rows}:
        raise ValueError('Exactly one unchanged record per provider in the whole group required')
    payment=review['payments'][0]
    for row,ref in zip(rows,review['replaces'],strict=True):
        raw=row['record']
        if (row['record_sha256']!=ref['record_sha256'] or identity(raw)!=row['record_sha256']
                or raw.get('record_date')!=payment['record_date']
                or raw.get('pay_date',raw.get('payable_date'))!=payment['pay_date']
                or row['effective_date']!=review['ex_date']
                or raw.get('due_bill_on_date') or raw.get('due_bill_off_date')):
            raise ValueError('Identical original dates, source bytes and ordinary entitlement required')
        if (row['provider']=='massive' and raw.get('currency')!='USD'
                or row['provider']=='alpaca' and (raw.get('foreign') is not False or raw.get('special') is not False)):
            raise ValueError('Known matching domestic USD cash units required')
    amounts=[Decimal(str(r['term'])) for r in rows]
    if any(not a.is_finite() or a<=0 for a in amounts):raise ValueError('Positive finite amounts required')
    precise=min(amounts,key=lambda a:a.as_tuple().exponent)
    rounded=max(amounts,key=lambda a:a.as_tuple().exponent)
    quantum=Decimal(1).scaleb(rounded.as_tuple().exponent)
    if (quantum>Decimal('.0001') or precise.as_tuple().exponent>=rounded.as_tuple().exponent
            or precise.quantize(quantum,rounding=ROUND_HALF_UP)!=rounded
            or abs(precise-rounded)>Decimal('.00005') or abs(precise-rounded)/precise>Decimal('.005')
            or Decimal(review['cash_per_share'])!=precise or Decimal(payment['cash_per_share'])!=precise):
        raise ValueError('Same distribution must agree at published decimal precision')
    return True


def compile_provider_precision(originals,reviews,history,calendar,base_policy,proposal,precision_policy):
    if len(reviews)!=1:raise ValueError('Exactly the finite remaining precision review required')
    review=reviews[0];validate_provider_precision(originals,review,precision_policy)
    actions,leaves,pending=compile_dividend_resolutions(originals,reviews,history,calendar,base_policy,proposal)
    pid=identity(precision_policy)
    for event in actions:
        old=event['action']
        action=ReconstructionAction(**{k:old[k] for k in
            ('event_id','effective_at','available_at','price_factor','volume_factor','source_identity')},
            admission_policy_identity=pid)
        event.update(action=serialized_action(action),admission_basis=BASIS,admission_policy_identity=pid,
            cash_amount_basis='paired_provider_decimal_precision',primary_amount_verified=False,
            primary_unit_evidence_identity=review['primary_unit_evidence_identity'])
        for leaf in leaves:
            if leaf['compiled_event_id']==action.event_id:
                leaf.update(policy_identity=pid,source_identity=identity(event),
                    date_basis='matching_original_provider_dates',cash_amount_basis='paired_provider_decimal_precision',
                    primary_amount_verified=False)
                leaf['event_id']='stock-cash:'+identity({k:v for k,v in leaf.items() if k!='event_id'})
    return actions,leaves,pending
