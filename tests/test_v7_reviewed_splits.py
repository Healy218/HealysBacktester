from copy import deepcopy
import json

import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.action_inventory import candidate
from nn_meta.v7.causal_daily import returns
from nn_meta.v7.causal_prices import CausalPriceHistory
from nn_meta.v7.ordinary_actions import price_action
from nn_meta.v7.reviewed_splits import compile_reviewed_splits
from nn_meta.v7.storage import identity


def fixture():
    cal=SessionCalendar(dict(coverage_start='2024-06-11',coverage_end='2024-06-13',
        sessions=[dict(date=d,open='09:30',close='16:00') for d in
                  ['2024-06-11','2024-06-12','2024-06-13']]))
    records=[('massive','splits',dict(id='m',ticker='ABC',execution_date='2024-06-12',
        adjustment_type='stock_dividend',split_from=1,split_to=2)),
        ('alpaca','forward_splits',dict(id='a',symbol='ABC',ex_date='2024-06-12',old_rate=1,new_rate=2))]
    rows=[candidate(p,k,r,scoped_symbols={'ABC'},start=cal.start,end=cal.end,
        source={'receipt':'original'}) for p,k,r in records]
    h=pd.DataFrame([dict(stock_ticker='ABC',source_date=d,security_id='sid',identity_span='span',
        session_open_ns=cal.bounds(d)[0].tz_localize('UTC').value,
        available_ns=cal.bounds(d)[1].tz_localize('UTC').value,raw_close=c,observed_minutes=390)
        for d,c in [('2024-06-11',100.),('2024-06-12',51.)]])
    review=dict(schema='v7-reviewed-same-share-split-v1',symbol='ABC',effective_date='2024-06-12',
        security_id='sid',new_shares_per_old_share='2',conclusion='same_share_class_forward_split',
        evidence_identity='primary-notice',publication_available_at='2024-05-24T04:00Z',
        other_security_entitlement=False,cash_entitlement=0,
        replaces=[{k:r[k] for k in ('provider','kind','action_id','record_sha256')} for r in rows])
    return rows,[review],h,cal


def test_exact_review_reaches_causal_consumers_and_preserves_pre_split_prefix():
    rows,reviews,h,cal=fixture()
    events,pending=compile_reviewed_splits(rows,reviews,h,cal)
    assert len(events)==1 and not pending
    action=price_action(json.loads(json.dumps(events[0])))
    assert action.price_factor==.5 and action.volume_factor==2
    assert events[0]['publication_verified'] and not events[0]['full_security_admitted']
    result=returns(h,[action],cal,security_id='sid',start=cal.start,end='2024-06-12',action_evidence_identity='review')
    assert result.simple_return.iloc[-1]==pytest.approx(.02)
    raw=pd.DataFrame({k:[100.,51.] for k in ['Open','High','Low','Close']},
        index=pd.to_datetime(h.available_ns,utc=True)-pd.Timedelta(minutes=1))
    raw['Volume']=[10.,20.];raw['available_at']=pd.to_datetime(h.available_ns,utc=True).to_numpy()
    chart=CausalPriceHistory(raw,[action],security_id='sid')
    before=pd.Timestamp('2024-06-11T20:00Z')
    pd.testing.assert_frame_equal(chart.view(before),CausalPriceHistory(raw,[],security_id='sid').view(before))
    after=chart.view(pd.Timestamp('2024-06-12T20:00Z'))
    assert after.Close.tolist()==[50.,51.] and after.Volume.tolist()==[20.,20.]


def test_no_global_type_conversion_and_untouched_pending_records():
    rows,_,h,cal=fixture()
    original=deepcopy(rows)
    assert compile_reviewed_splits(rows,[],h,cal)==([],original)


@pytest.mark.parametrize('change',['warrant','cash','fractional','wrong_ratio','wrong_identity',
    'identity_gap','missing_prior','wrong_clock','late_publication','naive_publication',
    'duplicate_review','wrong_ref','single_provider','combined','payload','normalized'])
def test_reject_unsupported_or_changed_group_without_mutating_inputs(change):
    rows,reviews,h,cal=fixture();r=reviews[0]
    if change=='warrant':r['other_security_entitlement']=True
    if change=='cash':r['cash_entitlement']=1
    if change=='fractional':r['new_shares_per_old_share']='1.25'
    if change=='wrong_ratio':r['new_shares_per_old_share']='4'
    if change=='wrong_identity':r['security_id']='other'
    if change=='identity_gap':h.loc[0,'identity_span']=None
    if change=='missing_prior':h=h.iloc[1:]
    if change=='wrong_clock':h.loc[1,'session_open_ns']+=1
    if change=='late_publication':r['publication_available_at']='2024-06-12T14:00Z'
    if change=='naive_publication':r['publication_available_at']='2024-06-01'
    if change=='duplicate_review':reviews.append(deepcopy(r))
    if change=='wrong_ref':r['replaces'][0]['record_sha256']='changed'
    if change=='single_provider':rows.pop()
    if change=='combined':
        rows.append(candidate('alpaca','spin_offs',dict(id='spin',source_symbol='ABC',effective_date='2024-06-12'),
            scoped_symbols={'ABC'},start=cal.start,end=cal.end,source={'receipt':'original'}))
    if change=='payload':rows[0]['record']['split_to']=4
    if change=='normalized':rows[0]['term']='4'
    original=deepcopy(rows)
    with pytest.raises(ValueError):compile_reviewed_splits(rows,reviews,h,cal)
    assert rows==original
