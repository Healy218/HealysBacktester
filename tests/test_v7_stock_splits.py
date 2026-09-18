from copy import deepcopy
from types import SimpleNamespace

import pytest

from nn_meta.v7.physical import PhysicalPolicy
from nn_meta.v7.portfolio import portfolio_replay
from nn_meta.v7.execution import QuotePolicy
from tests.test_v7_physical import ledger,ns,buy,evidence,stock_fill,calendar
from tests.test_v7_stock_cash import event as cash_event,purchase


def event(day='2024-05-28',ratio=2):
    clock=ns(day,'13:30')
    import pandas as pd
    return dict(symbol='SPY',security_id='SPY-id',effective_date=day,category='split',
        new_shares_per_old_share=str(ratio),cash_amount=None,cash_units=None,
        admission_basis='reviewed_publication',publication_verified=True,full_security_admitted=False,
        publication_available_at='2024-05-01T04:00:00+00:00',review_identity='review',evidence_identity='source',
        action=dict(event_id='reviewed-split:review',source_identity='review',
            available_at='2024-05-01T04:00:00+00:00',effective_at=pd.Timestamp(clock,tz='UTC').isoformat(),
            price_factor=1/ratio,volume_factor=ratio))


def test_unsettled_funded_purchase_splits_without_changing_payable_and_later_dividend_uses_new_units():
    book=ledger();purchase(book,quantity=10.5)
    e=event();before=book.available_cash;payable=book.commitments['inventory']['cash_delta']
    assert book.apply_stock_split(e,ns('2024-05-28','13:30'))==10.5
    assert book.available_cash==before and book.cash==100000.
    assert book.commitments['inventory']['cash_delta']==payable
    assert book.commitments['inventory']['shares']==21.
    book.settle(ns('2024-05-29','13:30'))
    assert book.shares['SPY','SPY-id']==21.
    c=cash_event();c.update(ex_date='2024-05-30',record_date='2024-05-30',
        effective_ns=ns('2024-05-30','13:30'),available_ns=ns('2024-05-30','13:30'))
    assert book.accrue_stock_cash(c,c['effective_ns'])==pytest.approx(9.24)
    book.reconcile()


def test_settled_inventory_split_does_not_rescale_already_accrued_cash():
    book=ledger();purchase(book,quantity=10.,clock=ns('2024-05-20','14:00'))
    book.settle(ns('2024-05-23','13:30'));c=cash_event()
    book.accrue_stock_cash(c,c['effective_ns']);before=deepcopy(book.cash_receivables)
    book.apply_stock_split(event('2024-05-29'),ns('2024-05-29','13:30'))
    assert book.shares['SPY','SPY-id']==20. and book.cash_receivables==before
    assert book.release_stock_cash(c,c['release_ns'])==4.4
    book.reconcile()


@pytest.mark.parametrize('phase',['pending','settled','sold'])
def test_call_delivery_changes_stock_units_but_retains_funding_and_completed_sale(phase):
    book=ledger();contract=buy(book)
    assert book.expire('a',ns('2024-05-24','21:00'),**evidence(contract))=='exercise_committed'
    day='2024-05-28'
    if phase!='pending':book.settle(ns('2024-05-30','13:30'));day='2024-05-31'
    if phase=='sold':book.liquidate_stock('a',stock_fill())
    cash=book.cash;commitments=deepcopy(book.commitments)
    delta=book.apply_stock_split(event(day),ns(day,'13:30'))
    assert book.cash==cash
    if phase=='sold':
        assert delta==0 and book.commitments==commitments
    else:
        assert delta==100 and book.positions['a']['deliverable_shares']==200
        if phase=='pending':
            assert book.commitments['a']['shares']==200
            assert book.commitments['a']['cash_delta']==commitments['a']['cash_delta']
    book.reconcile()


@pytest.mark.parametrize('change',['open_option','wrong_clock','duplicate','ratio','source','late','symbol','after_trade'])
def test_unreviewed_or_mistimed_splits_fail_before_mutation(change):
    book=ledger();e=event();clock=ns('2024-05-28','13:30')
    if change=='open_option':buy(book)
    else:purchase(book)
    if change=='wrong_clock':clock+=1
    if change=='duplicate':book.apply_stock_split(e,clock)
    if change=='ratio':e['new_shares_per_old_share']='3'
    if change=='source':e['review_identity']='changed'
    if change=='late':e['action']['available_at']='2024-05-29T04:00Z'
    if change=='symbol':e['symbol']='OTHER'
    if change=='after_trade':
        book.events[-1]['sip_timestamp']=clock
        book.last_clock=clock
    before=deepcopy(book.__dict__)
    with pytest.raises(ValueError):book.apply_stock_split(e,clock)
    for key in ('cash','positions','commitments','shares','events','last_clock','applied_stock_splits'):
        assert book.__dict__[key]==before[key]


def test_shared_portfolio_sells_post_split_quantity_with_cash_and_dividend_reconciled():
    class Options:
        def mark(self,contract,clock):return dict(price=1.,sip_timestamp=clock)
    class Stocks:
        def mark(self,symbol,clock):
            return dict(security_id='SPY-id',capture_identity='stock',sip_timestamp=clock,bid=55.)
        def first_fill(self,symbol,clock,**kwargs):
            assert kwargs['quantity']==200.
            return dict(stock_fill(symbol,clock),price=55.)
    decision=ns('2024-05-23','14:59');contract='SPY240524C00100000';c=cash_event()
    c.update(ex_date='2024-05-29',record_date='2024-05-29',effective_ns=ns('2024-05-29','13:30'),available_ns=ns('2024-05-29','13:30'))
    context=SimpleNamespace(settlement_calendar=calendar(),policy=PhysicalPolicy(),stock_archive=Stocks(),
        exercise_clock=lambda contract:ns('2024-05-24','21:00'),expiry_evidence=evidence,splits=[event()],cash_entitlements=[c])
    proposal=dict(proposal_id='a',symbol='SPY',security_id='SPY-id',decision_ns=decision,score=1.,score_available_ns=decision,
        path=dict(proposal_id='a',capture_complete=True,label_complete=False,label_end_ns=None,
            fills=[dict(contract=contract,side='buy',price=1.,decision_ns=decision,sip_timestamp=decision+1_000_000_000)]))
    clocks=[decision,ns('2024-05-24','21:00'),ns('2024-05-28','13:30'),c['effective_ns'],
        ns('2024-05-30','13:30'),ns('2024-05-31','13:30'),ns('2024-06-03','13:30')]
    result=portfolio_replay([proposal],clocks,Options(),fraction=.001,physical=context,policy=QuotePolicy(fee=0.,slippage=0.))
    assert result['complete']
    assert result['cash']==pytest.approx(100000.-100.-10000.+11000.*.9985+88.)
    assert next(e for e in result['fills'] if e.get('kind')=='stock_sale')['shares']==200.
