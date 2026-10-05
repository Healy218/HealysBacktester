import numpy as np
import pandas as pd
import pytest
from nn_meta.etfe.option_features import compute_window,NAMES,MINUTE

AT=pd.Timestamp('2024-01-19T15:00Z');T=AT.value-2*MINUTE;S='SPY240119C00475000'


def trade(second,price,size=1,**kw):
    return dict(symbol=S,timestamp_ns=T+int(second*1e9),price=price,size=size,condition='I',**kw)


def bar(**kw):
    return dict(symbol=S,timestamp_ns=T,vwap=2.,volume=4,trade_count=4,**kw)


def cov():return {T:dict(trade_transport_complete=True,bar_transport_complete=True)}


def compute(trades,bars=None,coverage=None):
    return compute_window(S,AT,1,trades,[bar()] if bars is None else bars,cov() if coverage is None else coverage)


def test_hand_worked_ten_fields_and_leading_equal_signs():
    r=compute([trade(1,2,1),trade(2,2,2),trade(3,3,3),trade(4,2,4)])
    v=[r['values'][n] for n in NAMES]
    np.testing.assert_allclose(v,[10000/2.3,np.std([1,2,3,4])/2.5,1,60,1/60,4/60,10/60,1500,-.1,.7])
    assert not r['model_feature_admitted'] and not any(r['missing'].values())


def test_condition_exclusions_preserve_audit_and_no_cross_window_tick():
    excluded=trade(2,1000,1000);excluded['condition']='v'
    before=trade(-1,100)
    r=compute([before,trade(1,2,2),excluded,trade(3,3,3)])
    assert r['values'][NAMES[5]]==2/60 and r['audit']['excluded_condition_volume']==1000
    assert r['values'][NAMES[8]]==.6


def test_equal_time_order_invariance_and_ambiguous_last():
    a,b=trade(1,2),trade(1,3)
    r=compute([a,b]);s=compute([b,a])
    assert r==s
    assert r['reasons'][NAMES[7]]=='ambiguous_last_trade'
    assert r['reasons'][NAMES[8]]==r['reasons'][NAMES[9]]=='ambiguous_order'
    r=compute([a,b,trade(2,4)])
    assert r['values'][NAMES[7]] is not None and r['values'][NAMES[8]] is None


def test_capture_is_not_no_trade_and_proof_must_be_known():
    r=compute([],[]);assert all(r['missing'].values())
    c=cov();proof=dict(evidence_sha256='a'*64,start_ns=T,end_ns=T+MINUTE,available_at_ns=AT.value)
    c[T].update(trade_empty_evidence=proof,bar_empty_evidence=proof)
    r=compute([],[],c)
    for i in (2,4,5,6):assert r['values'][NAMES[i]]==0
    for i in (0,1,3,7,8,9):assert r['values'][NAMES[i]] is None
    proof['available_at_ns']+=1
    assert all(compute([],[],c)['missing'].values())


def test_later_availability_and_missing_bar_do_not_fabricate_values():
    r=compute([trade(1,2,available_at_ns=AT.value+1)])
    assert r['reasons'][NAMES[5]]=='not_yet_available'
    r=compute([trade(1,2)],[])
    assert r['values'][NAMES[5]]==1/60 and r['values'][NAMES[2]] is None
    r=compute([trade(1,2)],[bar(available_at_ns=AT.value+1)])
    assert r['reasons'][NAMES[2]]=='not_yet_available'


@pytest.mark.parametrize('minutes',[1,5,15])
def test_half_open_window_future_invariance_and_capture_gap(minutes):
    start=AT.value-(minutes+1)*MINUTE
    c={t:dict(trade_transport_complete=True,bar_transport_complete=True) for t in range(start,AT.value-MINUTE,MINUTE)}
    trades=[dict(trade(1,2),timestamp_ns=t+1) for t in c]
    bars=[dict(bar(),timestamp_ns=t) for t in c]
    base=compute_window(S,AT,minutes,trades,bars,c)
    future=dict(trade(1,9000),timestamp_ns=AT.value-MINUTE)
    assert base==compute_window(S,AT,minutes,trades+[future],bars+[dict(bar(),timestamp_ns=AT.value)],c)
    del c[start]
    assert all(compute_window(S,AT,minutes,trades,bars,c)['missing'].values())


def test_bad_observations_and_duplicate_id_fail_closed():
    assert compute([trade(1,-2)])['reasons'][NAMES[0]]=='invalid_trade'
    assert compute([trade(1,2,native_trade_id='same'),trade(2,3,native_trade_id='same')])['reasons'][NAMES[0]]=='unresolved_trade_revision'
    with pytest.raises(ValueError,match='Repeated'):
        compute([trade(1,2,occurrence_id='same'),trade(2,3,occurrence_id='same')])
    assert compute([trade(1,2)],[bar(),bar()])['reasons'][NAMES[2]]=='ambiguous_bar_vintage'


def test_single_trade_and_excluded_only_window():
    r=compute([trade(1,2,3)])
    for i in (0,1,7,8,9):assert r['values'][NAMES[i]]==0
    excluded=trade(1,2,3);excluded['condition']=None
    r=compute([excluded])
    assert r['values'][NAMES[5]]==r['values'][NAMES[6]]==0
    assert r['values'][NAMES[0]] is None and r['audit']['excluded_condition']==1


def test_equal_final_prices_allow_last_ratio_but_not_signs():
    r=compute([trade(1,2),trade(2,3),trade(2,3)])
    assert r['values'][NAMES[7]] is not None and r['reasons'][NAMES[8]]=='ambiguous_order'


def test_empty_evidence_cannot_contradict_observations():
    c=cov();c[T]['trade_empty_evidence']=dict(evidence_sha256='a'*64,start_ns=T,end_ns=T+MINUTE,available_at_ns=AT.value)
    with pytest.raises(ValueError,match='conflicts'):compute([trade(1,2)],coverage=c)


def test_vwap_last_uses_stable_weighted_sum():
    prints=[trade(i+1,1.52,s) for i,s in enumerate([5,7,18,9,6,17,6,9])]
    r=compute(prints)
    # A constant price has zero VWAP displacement irrespective of trade sizes.
    assert r['values'][NAMES[7]]==pytest.approx(0,abs=1e-12)
