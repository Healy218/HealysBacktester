from copy import deepcopy

import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.cash_actions import compile_cash_actions
from nn_meta.v7.storage import identity


def fixture():
    calendar=SessionCalendar(dict(coverage_start='2024-09-12',coverage_end='2024-09-16',
        sessions=[dict(date=day,open='09:30',close='16:00') for day in
                  ['2024-09-12','2024-09-13','2024-09-16']]))
    candidates=[]
    for provider,identifier in [('massive','a'),('massive','b'),('massive','c'),('alpaca','d')]:
        record=dict(id=identifier,rate=.22)
        candidates.append(dict(provider=provider,kind='cash_dividends',action_id=identifier,
            record=record,record_sha256=identity(record),scoped_symbols=['ABC'],subject_symbol='ABC',
            effective_date='2024-09-13',category='cash'))
    review=dict(event_id='reviewed-ABC',symbol='ABC',security_id='security',
        effective_date='2024-09-13',currency='USD',cash_units='per_common_share',
        cash_amount='0.44',publication_available_at='2024-08-07T04:00Z',
        evidence_identity='retained-review',replaces=[{k:r[k] for k in
            ['provider','kind','action_id','record_sha256']} for r in candidates])
    stock=pd.DataFrame([dict(stock_ticker='ABC',source_date=day,security_id='security',
        raw_close=close,observed_minutes=390,
        available_ns=calendar.bounds(day)[1].tz_localize('UTC').value)
        for day,close in [('2024-09-12',40.01),('2024-09-13',39.50)]])
    return candidates,[review],stock,calendar


def test_whole_event_replaces_all_components_once_and_binds_prior_close():
    events,pending=compile_cash_actions(*fixture())
    assert not pending and len(events)==1
    event=events[0]
    assert event['cash_amount']=='0.44'
    assert len(event['replaces'])==4
    assert event['action']['price_factor']==pytest.approx(1-.44/40.01)
    assert event['action']['volume_factor']==1
    assert event['action']['available_at']=='2024-09-12T20:00:00+00:00'
    assert not event['full_security_admitted']


@pytest.mark.parametrize('change',['partial','duplicate_reference','duplicate_review','changed_hash','changed_payload'])
def test_inexact_replacements_cannot_double_adjust(change):
    candidates,reviews,stock,calendar=fixture()
    if change=='partial':reviews[0]['replaces'].pop()
    if change=='duplicate_reference':reviews[0]['replaces'].append(reviews[0]['replaces'][0])
    if change=='duplicate_review':
        reviews.append(deepcopy(reviews[0]));reviews[-1]['event_id']='second-review'
    if change=='changed_hash':reviews[0]['replaces'][0]['record_sha256']='other'
    if change=='changed_payload':candidates[0]['record']['rate']=.33
    with pytest.raises(ValueError):compile_cash_actions(candidates,reviews,stock,calendar)


def test_simultaneous_split_or_complex_event_requires_combined_review():
    candidates,reviews,stock,calendar=fixture()
    extra=deepcopy(candidates[0]);extra.update(action_id='split',category='split',kind='splits')
    candidates.append(extra)
    with pytest.raises(ValueError,match='entire event group'):
        compile_cash_actions(candidates,reviews,stock,calendar)
    reviews[0]['replaces'].append({k:extra[k] for k in ['provider','kind','action_id','record_sha256']})
    with pytest.raises(ValueError,match='combined review'):
        compile_cash_actions(candidates,reviews,stock,calendar)


@pytest.mark.parametrize('change',['missing_prior','wrong_identity','missing_close','wrong_clock','late_publication','wrong_units'])
def test_no_fabricated_price_identity_clock_or_units(change):
    candidates,reviews,stock,calendar=fixture()
    if change=='missing_prior':stock=stock.iloc[1:]
    if change=='wrong_identity':stock.loc[0,'security_id']='other'
    if change=='missing_close':stock.loc[0,'raw_close']=float('nan')
    if change=='wrong_clock':stock.loc[0,'available_ns']+=1
    if change=='late_publication':reviews[0]['publication_available_at']='2024-09-16T00:00Z'
    if change=='wrong_units':reviews[0]['cash_units']='per_ADS'
    with pytest.raises(ValueError):compile_cash_actions(candidates,reviews,stock,calendar)


def test_unreviewed_records_remain_pending_and_future_events_do_not_change_factor():
    candidates,reviews,stock,calendar=fixture()
    expected,_=compile_cash_actions(candidates,reviews,stock,calendar)
    future=deepcopy(candidates[0]);future.update(action_id='future',effective_date='2024-09-16')
    actual,pending=compile_cash_actions(candidates+[future],reviews,stock,calendar)
    assert actual==expected and pending==[future]
    events,pending=compile_cash_actions(candidates,[],stock,calendar)
    assert events==[] and pending==candidates
