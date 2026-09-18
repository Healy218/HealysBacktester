from copy import deepcopy
from types import SimpleNamespace

import pytest

from nn_meta.v7.physical import PhysicalPolicy
from nn_meta.v7.portfolio import portfolio_replay
from tests.test_v7_physical import ledger, calendar, ns, stock_fill, buy, evidence


def rename(clock=None):
    return dict(schema='v7-reviewed-common-share-rename-v1',event_id='rename:review',
        security_id='SPY-id',share_class_figi='share-class',old_symbol='SPY',new_symbol='NEW',
        review_identity='review',evidence_identity='notice',prior_date='2024-05-29',
        effective_date='2024-05-30',effective_ns=clock or ns('2024-05-30','13:30'),
        available_ns=ns('2024-05-22'),share_quantity_factor=1,cash_delta=0,
        option_deliverables_admitted=False)


def test_funded_inventory_rename_preserves_cash_settlement_and_quantity():
    book=ledger();fill=stock_fill(clock=ns('2024-05-28','14:00'));fill['side']='buy'
    assert book.acquire_inventory('inventory','SPY','SPY-id',10.,fill)
    commitments=deepcopy(book.commitments);cash=book.cash
    affected=book.apply_stock_rename(rename(),rename()['effective_ns'])
    assert affected==['inventory'] and book.positions['inventory']['symbol']=='NEW'
    assert book.commitments==commitments and book.cash==cash
    book.settle(rename()['effective_ns'])
    assert book.shares=={('NEW','SPY-id'):10.} and book.cash==pytest.approx(cash-1101.65)
    assert book.reconcile()['pending_settlements']==0
    with pytest.raises(ValueError):book.apply_stock_rename(rename(),rename()['effective_ns'])


def test_settled_inventory_rekeys_without_changing_funded_cash():
    book=ledger();fill=stock_fill(clock=ns('2024-05-23','14:00'));fill['side']='buy'
    assert book.acquire_inventory('inventory','SPY','SPY-id',10.,fill)
    book.settle(ns('2024-05-29','13:30'))
    cash=book.cash
    book.apply_stock_rename(rename(),rename()['effective_ns'])
    assert book.shares=={('NEW','SPY-id'):10.} and book.cash==cash
    assert book.reconcile()['pending_settlements']==0


def test_open_options_reject_stock_only_notice_before_any_mutation():
    book=ledger();buy(book)
    before=deepcopy(book.__dict__)
    with pytest.raises(ValueError,match='separate corporate-action'):
        book.apply_stock_rename(rename(),rename()['effective_ns'])
    for key in ('cash','positions','events','last_clock','applied_stock_renames'):
        assert book.__dict__[key]==before[key]


def test_delivered_call_shares_keep_cost_and_liquidate_under_new_symbol():
    book=ledger();contract=buy(book)
    assert book.expire('a',ns('2024-05-24','21:00'),**evidence(contract))=='exercise_committed'
    book.settle(ns('2024-05-30','13:30'))
    prior=deepcopy(book.positions['a'])
    book.apply_stock_rename(rename(),rename()['effective_ns'])
    assert book.positions['a']=={**prior,'symbol':'NEW'}
    assert book.liquidate_stock('a',stock_fill(symbol='NEW'))==pytest.approx(10983.5)
    book.settle(ns('2024-06-03','13:30'))
    assert book.reconcile()['cash']==pytest.approx(100883.5)


@pytest.mark.parametrize('change',['early','late','factor','cash','options','unknown_phase'])
def test_invalid_rename_cannot_change_funded_resources(change):
    book=ledger();event=rename();clock=event['effective_ns']
    if change=='early':clock-=1
    if change=='late':clock+=1
    if change=='factor':event['share_quantity_factor']=2
    if change=='cash':event['cash_delta']=1
    if change=='options':event['option_deliverables_admitted']=True
    if change=='unknown_phase':
        buy(book);book.positions['a']['phase']='cash_merger_pending'
    before=deepcopy(book.__dict__)
    with pytest.raises(ValueError):book.apply_stock_rename(event,clock)
    for key in ('cash','positions','events','last_clock','applied_stock_renames'):
        assert book.__dict__[key]==before[key]


def test_portfolio_schedules_notice_before_same_clock_mark():
    event=rename()
    physical=SimpleNamespace(settlement_calendar=calendar(),policy=PhysicalPolicy(),stock_archive=None,renames=[event])
    result=portfolio_replay([], [event['effective_ns']-1,event['effective_ns']],None,physical=physical)
    assert result['fills'][0]['kind']=='stock_ticker_change'
    assert result['fills'][0]['sip_timestamp']==event['effective_ns']
    assert result['cash']==100000. and result['complete']
