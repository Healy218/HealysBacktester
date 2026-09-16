import math
import json
import pandas as pd
import pytest
from options.paper_pricing import option_midpoint, MIDPOINT_POLICY
from tests.test_v7_execution import tape, quote


def test_provider_midpoint_precedes_computed_average_and_last_is_not_mid():
    assert option_midpoint(dict(bid=3.15,ask=3.9,last=2.))['price']==pytest.approx(3.525)
    result=option_midpoint(dict(bid_price=3.15,ask_price=3.9,midpoint=3.53,last_price=10.))
    assert result['price']==3.53 and result['price_source']=='provider:midpoint'
    for changed in [dict(mid=0),dict(mid=4.),dict(mid=float('nan')),dict(mid=True),dict(mid=3.5,midpoint=3.6),dict(bid=4.)]:
        with pytest.raises(ValueError):option_midpoint(dict(bid=3.15,ask=3.9,**changed) if 'bid' not in changed else dict(bid=4.,ask=3.9))


def test_same_quote_produces_identical_v7_buy_sell_and_mark_prices():
    row=quote(2_000_000_000,bid=3.15,ask=3.9);row['mid']=3.53
    book=tape([row]);buy=book.first_fill(0,side='buy');sell=book.first_fill(0,side='sell');mark=book.mark(3_000_000_000)
    assert buy['price']==sell['price']==mark['price']==3.53
    assert buy['bid']==3.15 and buy['ask']==3.9 and buy['simulated']
    assert buy['pricing_policy']==MIDPOINT_POLICY



def test_v7_wide_unchanged_quote_has_no_spread_loss_in_fill_or_equity():
    from datetime import date
    from nn_meta.v7.execution import CashLedger, QuotePolicy
    start=pd.Timestamp('2022-03-07T15:00Z').value
    book=tape([quote(start+2_000_000_000,bid=3.15,ask=3.9),
               quote(start+5_000_000_000,bid=3.15,ask=3.9)],start=start,end=start+100_000_000_000)
    ledger=CashLedger(policy=QuotePolicy(fee=0.,slippage=0.))
    buy=book.first_fill(start,side='buy')
    ledger.buy('one','SPY',buy,equity=100000.,decision_date=date(2022,3,7))
    assert ledger.equity(start+3_000_000_000,{buy['contract']:book})==pytest.approx(100000.)
    sell=book.first_fill(start+3_000_000_000,side='sell')
    ledger.sell('one',sell)
    assert ledger.reconcile()['cash']==pytest.approx(100000.)
