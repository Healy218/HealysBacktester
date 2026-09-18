from copy import deepcopy
import pandas as pd
import pytest
from nn_meta.v7.dividend_boundaries import validate_boundary_identity,observed_day,add_boundary_view
from nn_meta.v7.storage import identity
from tests.test_v7_dividend_resolution import case


def witnesses():
    r=dict(ticker='ABC',cik='123',type='CS',market='stocks',locale='us',currency_name='usd',
           primary_exchange='XNYS',composite_figi='successor',share_class_figi='new-class',active=True)
    request=dict(source_symbol='ABC',prior_date='2024-06-11',ex_date='2024-06-12',security_id='successor',
                 mode='separate_cash_security',changes_trading_eligibility=False,bridges_reorganization=False)
    return request,[r,deepcopy(r)]


def test_separate_successor_never_aliases_existing_security():
    request,rows=witnesses();assert validate_boundary_identity(request,rows,{'predecessor'})
    request['security_id']='predecessor'
    with pytest.raises(ValueError):validate_boundary_identity(request,rows,{'predecessor'})


@pytest.mark.parametrize('change',['share_class','ticker','inactive','scope','bridge','mode'])
def test_boundary_identity_fails_closed(change):
    request,rows=witnesses()
    if change=='share_class':rows[1]['share_class_figi']='other'
    elif change=='ticker':rows[1]['ticker']='OTHER'
    elif change=='inactive':rows[1]['active']=False
    elif change=='scope':request['changes_trading_eligibility']=True
    elif change=='bridge':request['bridges_reorganization']=True
    else:request['mode']='inferred'
    with pytest.raises(ValueError):validate_boundary_identity(request,rows,{'predecessor'})


def test_cusip_requires_missing_figi_and_primary_identity():
    request,rows=witnesses()
    for r in rows:r.pop('composite_figi');r.pop('share_class_figi')
    request.update(mode='primary_cusip_cash_security',cusip='123456789',security_id='CUSIP:123456789',
                   cik='123',primary_identity_evidence=[{'capture':'issuer-cusip'}])
    assert validate_boundary_identity(request,rows,{'predecessor'})
    rows[1]['composite_figi']='known'
    with pytest.raises(ValueError):validate_boundary_identity(request,rows,{'predecessor'})


def test_named_raw_day_uses_only_completed_regular_minutes():
    calendar=case()[3]
    raw=pd.DataFrame(dict(timestamp=pd.to_datetime(['2024-06-11 13:29Z','2024-06-11 13:30Z','2024-06-11 19:59Z','2024-06-11 20:00Z']),
        Open=[90.,100.,102.,120.],High=[91.,101.,103.,121.],Low=[89.,99.,101.,119.],Close=[90.,100.,102.,120.],Volume=[1.,2.,3.,4.]))
    r=observed_day(raw,calendar,'ABC','2024-06-11')
    assert r['observed_minutes']==2 and r['raw_close']==102. and r['raw_volume']==5.
    raw.loc[1,'Low']=200
    with pytest.raises(ValueError):observed_day(raw,calendar,'ABC','2024-06-11')


def test_predecessor_holdings_do_not_receive_successor_cash():
    from nn_meta.v7.dividend_resolution import compile_dividend_resolutions
    from nn_meta.v7.physical import PhysicalLedger,SettlementCalendar
    from nn_meta.v7.execution import QuotePolicy
    from tests.test_v7_physical import stock_fill,ns
    args=case();actions,cash,_=compile_dividend_resolutions(*args);calendar=args[3]
    schedule=SettlementCalendar(dict(schema='v7-settlement-calendar-v1',business_dates=sorted(calendar.sessions),
        coverage_start=calendar.start,coverage_end=calendar.end,source_identity='fixture'),calendar)
    book=PhysicalLedger(capital=100000.,settlement_calendar=schedule,policy=QuotePolicy(fee=0.,slippage=0.))
    fill=stock_fill('ABC',ns('2024-06-11','14:00'));fill.update(side='buy',security_id='predecessor')
    assert book.acquire_inventory('funded','ABC','predecessor',10,fill)
    assert book.accrue_stock_cash(cash[0],cash[0]['effective_ns'])==0
    assert book.reconcile()['cash_receivables']==0
