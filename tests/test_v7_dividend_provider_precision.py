from copy import deepcopy
import pytest
from nn_meta.v7.dividend_provider_precision import validate_provider_precision,compile_provider_precision
from nn_meta.v7.storage import identity


def fixture():
    originals=[]
    for provider,amount in [('alpaca','.025932'),('massive','.0259')]:
        raw=dict(record_date='2026-09-03',currency='USD',foreign=False,special=False)
        raw['payable_date' if provider=='alpaca' else 'pay_date']='2026-09-04'
        originals.append(dict(provider=provider,kind='cash_dividends' if provider=='alpaca' else 'dividends',
            action_id=provider,record=raw,record_sha256=identity(raw),category='cash',subject_symbol='ETHE',
            effective_date='2026-09-03',term=amount))
    refs=[{k:r[k] for k in ('provider','kind','action_id','record_sha256')} for r in originals]
    e={'capture':'issuer-unit-proof'}
    review=dict(symbol='ETHE',ex_date='2026-09-03',replaces=refs,evidence=[e],primary_unit_evidence_identity=identity(e),
        amount_basis='paired_provider_decimal_precision',primary_amount_verified=False,cash_per_share='.025932',
        payments=[dict(record_date='2026-09-03',pay_date='2026-09-04',cash_per_share='.025932')])
    policy=dict(schema='v7-finite-dividend-provider-precision-v1',status='authorized_implementation',authorization='Finite fixture',
        primary_amount_verified=False,withholdings_and_fees_modeled=False,scope_change=False,replaces=deepcopy(refs))
    return originals,review,policy


def test_rounding_agreement_keeps_the_exact_original():
    args=fixture();before=deepcopy(args);assert validate_provider_precision(*args);assert args==before


@pytest.mark.parametrize('change',['foreign','currency','pay','real_conflict','coarse','invented','primary_claim','duplicate','other_symbol','unit_proof'])
def test_precision_rule_cannot_resolve_economic_or_source_conflicts(change):
    rows,r,p=fixture()
    if change=='foreign':rows[0]['record']['foreign']=True
    elif change=='currency':rows[1]['record']['currency']='CAD'
    elif change=='pay':rows[1]['record']['pay_date']='2026-09-05'
    elif change=='real_conflict':rows[1]['term']='.0260'
    elif change=='coarse':rows[1]['term']='.03'
    elif change=='invented':r['cash_per_share']='.025931'
    elif change=='primary_claim':r['primary_amount_verified']=True
    elif change=='duplicate':rows.append(deepcopy(rows[0]));r['replaces'].append(deepcopy(r['replaces'][0]));p['replaces']=deepcopy(r['replaces'])
    elif change=='other_symbol':r['symbol']='OTHER'
    else:r['primary_unit_evidence_identity']='unbound'
    # Rebinding a changed payload cannot make a currency/date conflict acceptable.
    if change in ('foreign','currency','pay'):
        for row,ref in zip(rows,r['replaces'],strict=True):
            row['record_sha256']=identity(row['record']);ref['record_sha256']=row['record_sha256']
        p['replaces']=deepcopy(r['replaces'])
    with pytest.raises(ValueError):validate_provider_precision(rows,r,p)
