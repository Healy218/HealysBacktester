"""Explicit authorized native-currency dividend reconstruction with official FX."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
from nn_meta.v7.storage import identity


def modeled_usd(native_amount, currency, ex_date, observations):
    if currency not in ('CAD', 'BRL'):
        raise ValueError('Modeled conversion is limited to CAD and BRL')
    if len({r['d'] for r in observations}) != len(observations):
        raise ValueError('Unique official FX observation dates required')
    keys = ['FXUSDCAD'] + (['FXBRLCAD'] if currency == 'BRL' else [])
    prior = [r for r in observations if r['d'] < ex_date and all(r.get(k, {}).get('v') for k in keys)]
    if not prior:
        raise ValueError('Published preceding FX observation required')
    row = max(prior, key=lambda r: r['d'])
    if not 0 < (date.fromisoformat(ex_date)-date.fromisoformat(row['d'])).days <= 7:
        raise ValueError('Stale or same-day FX cannot price an ex-open')
    amount = Decimal(str(native_amount)); usd = Decimal(row['FXUSDCAD']['v'])
    native = Decimal(1) if currency == 'CAD' else Decimal(row['FXBRLCAD']['v'])
    if not all(x.is_finite() and x > 0 for x in (amount, usd, native)):
        raise ValueError('Positive finite native amount and official FX required')
    with localcontext() as context:
        context.prec = 40
        result = (amount*native/usd).quantize(Decimal('.000000000001'), rounding=ROUND_HALF_UP)
    return str(result), dict(observation_date=row['d'], cad_per_usd=str(usd),
        cad_per_native=str(native), native_currency=currency, native_amount=str(amount),
        rule='last_official_daily_observation_strictly_before_ex_date', actual_conversion=False)


def validate_fx_review(review, observations, policy):
    if (policy.get('schema') != 'v7-modeled-dividend-fx-policy-v1'
            or policy.get('status') != 'user_authorized' or not policy.get('authorization')
            or review['symbol'] not in policy['symbols']
            or policy.get('actual_depositary_conversion_claimed') is not False
            or policy.get('withholdings_and_fees_modeled') is not False
            or review.get('amount_basis') != 'authorized_modeled_official_fx'
            or review.get('fx_policy_identity') != identity(policy)
            or review.get('fx_evidence_identity') not in {identity(e) for e in review['evidence']}):
        raise ValueError('Exact authorized and source-bound modeled FX review required')
    for payment in review['payments']:
        model = payment['fx_model']
        amount, expected = modeled_usd(model['native_amount'], model['native_currency'], review['ex_date'], observations)
        if model != expected or payment['cash_per_share'] != amount:
            raise ValueError('Cash model differs from preceding official FX reconstruction')
    return True


def label_fx_events(actions, leaves, reviews):
    by_review = {identity(r): r for r in reviews}
    for action in actions:
        review = by_review[action['review_identity']]
        action['cash_amount_basis'] = review['amount_basis']
        action['fx_policy_identity'] = review['fx_policy_identity']
        action['actual_depositary_conversion_claimed'] = False
        for leaf in leaves:
            if leaf['compiled_event_id'] == action['action']['event_id']:
                leaf['fx_model'] = review['payments'][leaf['dividend_component_index']]['fx_model']
                leaf['fx_policy_identity'] = review['fx_policy_identity']
                leaf['cash_amount_basis'] = review['amount_basis']
                leaf['source_identity'] = identity(action)
                leaf['event_id'] = 'stock-cash:'+identity({k:v for k,v in leaf.items() if k!='event_id'})
