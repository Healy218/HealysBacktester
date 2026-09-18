from copy import deepcopy
from decimal import Decimal
import pytest
from nn_meta.v7.dividend_fx import modeled_usd, validate_fx_review, label_fx_events
from nn_meta.v7.storage import identity


def observations():
    return [dict(d=d, FXUSDCAD={'v':u}, FXBRLCAD={'v':b}) for d,u,b in
        [('2026-06-01','1.4','.28'),('2026-06-02','1.25','.25'),('2026-06-03','2','.3')]]


def test_fx_uses_latest_prior_day_not_ex_day_or_final_payment_fx():
    amount, model = modeled_usd('.60','CAD','2026-06-03',observations())
    assert amount == '0.480000000000' and model['observation_date'] == '2026-06-02'
    amount, model = modeled_usd('1.3481426','BRL','2026-06-03',observations())
    assert amount == '0.269628520000'  # currencyPerDr already includes the ADR ratio.
    assert model['actual_conversion'] is False


@pytest.mark.parametrize('amount,currency,date', [('NaN','CAD','2026-06-03'),
    ('-1','BRL','2026-06-03'),('1','EUR','2026-06-03'),('1','CAD','2026-06-01'),('1','CAD','2026-06-20')])
def test_fx_rejects_invalid_or_unavailable_conversion(amount,currency,date):
    with pytest.raises(ValueError): modeled_usd(amount,currency,date,observations())


def test_fx_duplicate_observations_rejected():
    with pytest.raises(ValueError): modeled_usd('1','CAD','2026-06-03',observations()*2)


def fixture():
    policy=dict(schema='v7-modeled-dividend-fx-policy-v1',status='user_authorized',authorization='Use this modeled FX rule',symbols=['SU'],actual_depositary_conversion_claimed=False,withholdings_and_fees_modeled=False)
    e={'capture':'official-fx'}; amount,model=modeled_usd('.6','CAD','2026-06-03',observations())
    review=dict(symbol='SU',ex_date='2026-06-03',amount_basis='authorized_modeled_official_fx',
        fx_policy_identity=identity(policy),fx_evidence_identity=identity(e),evidence=[e],
        payments=[dict(cash_per_share=amount,fx_model=model)])
    return review,policy


def test_review_recomputes_and_binds_fx():
    review,policy=fixture(); assert validate_fx_review(review,observations(),policy)
    changed=deepcopy(review); changed['payments'][0]['cash_per_share']='.47'
    with pytest.raises(ValueError): validate_fx_review(changed,observations(),policy)
    changed=deepcopy(review); changed['payments'][0]['fx_model']['observation_date']='2026-06-01'
    with pytest.raises(ValueError): validate_fx_review(changed,observations(),policy)


def test_model_label_is_bound_into_price_source_and_cash_event():
    review,policy=fixture()
    actions=[dict(review_identity=identity(review),action={'event_id':'price'})]
    cash=[dict(compiled_event_id='price',dividend_component_index=0,event_id='old')]
    label_fx_events(actions,cash,[review])
    assert cash[0]['source_identity']==identity(actions[0])
    assert cash[0]['event_id']=='stock-cash:'+identity({k:v for k,v in cash[0].items() if k!='event_id'})
    assert cash[0]['fx_model']==review['payments'][0]['fx_model']
    assert actions[0]['actual_depositary_conversion_claimed'] is False
