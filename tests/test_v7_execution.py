from datetime import date
import hashlib
import pandas as pd
import pytest
from options.data.massive_ticks import canonical_bytes
from nn_meta.v7.execution import QuoteTape,QuotePolicy,QuoteUnavailable,CashLedger
from nn_meta.v7.evaluation import fold_masks
from nn_meta.session_calendar import SessionCalendar


def tape(rows,start=0,end=100_000_000_000):
    contract='SPY220311C00420000'
    manifest={'schema':'massive-option-ticks-v1','provider':'massive','contract':'O:'+contract,
              'kind':'quotes','start_ns':start,'end_ns':end,'complete':True,'records':len(rows),
              'records_sha256':hashlib.sha256(canonical_bytes(rows)).hexdigest()}
    return QuoteTape(rows,manifest,contract=contract)


def quote(t,bid=1.,ask=1.2):
    return {'sip_timestamp':t,'bid_price':bid,'ask_price':ask,'bid_size':2,'ask_size':3}


def test_after_decision_midpoint_fill_and_causal_midpoint_mark():
    q=tape([quote(0),quote(2_000_000_000),quote(80_000_000_000,bid=2,ask=2.1)])
    fill=q.first_fill(0,side='buy')
    assert fill['sip_timestamp']==2_000_000_000 and fill['price']==1.1
    assert q.mark(10_000_000_000)['price']==1.1
    assert q.mark(10_000_000_000)['bid']==1.
    with pytest.raises(QuoteUnavailable,match='fresh'):q.mark(50_000_000_000)


def test_invalid_latest_quote_cannot_use_older_market_and_absence_is_distinct():
    q=tape([quote(0),quote(2_000_000_000,bid=2,ask=1)])
    assert q.first_fill(0,side='buy') is None
    with pytest.raises(QuoteUnavailable,match='invalid'):q.mark(3_000_000_000)
    with pytest.raises(QuoteUnavailable,match='completely'):q.first_fill(80_000_000_000,side='buy')


def test_shared_cash_roll_costs_and_missing_exit_stays_open():
    ledger=CashLedger();contract='SPY220311C00420000'
    stamp=pd.Timestamp('2022-03-07T15:00Z').value
    fill={'contract':contract,'side':'buy','price':1.2,'sip_timestamp':stamp}
    assert ledger.buy('one','SPY',fill,equity=100000.,decision_date=date(2022,3,7))
    assert ledger.cash==90000
    assert not ledger.buy('duplicate','SPY',fill,equity=100000.,decision_date=date(2022,3,7))
    assert ledger.sell('one',None) is None and 'one' in ledger.positions
    proceeds=ledger.sell('one',{**fill,'side':'sell','price':1.3,'sip_timestamp':stamp+2_000_000_000})
    expected=10000/(1.2*1.0015)*1.3*.9985
    assert proceeds==pytest.approx(expected)
    assert ledger.reconcile()['cash']==pytest.approx(90000+expected)
    with pytest.raises(ValueError,match='1–9'):
        ledger.buy('bad','SPY',{**fill,'sip_timestamp':pd.Timestamp('2022-03-11T15:00Z').value},
                   equity=100000.,decision_date=date(2022,3,11))


def test_unsorted_quotes_and_invalid_prices_are_rejected():
    with pytest.raises(ValueError,match='ordered'):
        tape([quote(5),quote(3)])
    for price in (0,-1,float('nan'),float('inf'),True):
        ledger=CashLedger()
        with pytest.raises(ValueError,match='finite'):
            ledger.buy('bad','SPY',{'contract':'SPY220311C00420000','side':'buy','price':price,
                'sip_timestamp':pd.Timestamp('2022-03-07T15:00Z').value},equity=100000.,decision_date=date(2022,3,7))
        assert ledger.cash==100000. and not ledger.positions


def test_purchase_dte_uses_actual_fill_day_and_cannot_mark_before_purchase():
    ledger=CashLedger()
    fill={'contract':'SPY220311C00420000','side':'buy','price':1.,
          'sip_timestamp':pd.Timestamp('2022-03-11T14:00Z').value}
    with pytest.raises(ValueError,match='1–9'):
        ledger.buy('late','SPY',fill,equity=100000.,decision_date=date(2022,3,10))


def test_purge_uses_full_exit_horizon_and_excludes_unresolved_positions():
    days=pd.bdate_range('2024-01-01','2024-02-29').strftime('%Y-%m-%d')
    calendar=SessionCalendar({'coverage_start':days[0],'coverage_end':days[-1],
        'sessions':[{'date':d,'open':'09:30','close':'16:00'} for d in days]})
    rows=pd.DataFrame({'decision_at':['2024-01-03T15:00Z']*3+['2024-02-02T15:00Z'],
        'label_end':['2024-01-04T15:00Z','2024-02-02T15:00Z',None,'2024-02-05T15:00Z'],
        'label_complete':[True,True,False,True]})
    train,valid=fold_masks(rows,{'train_end':'2024-01-31','validation_start':'2024-02-01','validation_end':'2024-02-29'},calendar,embargo_sessions=2)
    assert train.tolist()==[True,False,False,False]
    assert valid.tolist()==[False,False,False,True]
