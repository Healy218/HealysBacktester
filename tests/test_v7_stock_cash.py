from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.ordinary_actions import compile_ordinary_actions
from nn_meta.v7.stock_cash import compile_cash_entitlements, POLICY_ID
from tests.test_v7_ordinary_actions import fixture,make_candidate
from tests.test_v7_physical import ledger,ns,stock_fill,buy,evidence,calendar
from nn_meta.v7.portfolio import portfolio_replay
from nn_meta.v7.physical import PhysicalPolicy
from nn_meta.v7.execution import QuotePolicy


def compiled_inputs():
    rows,reviews,history,_,ordinary_policy=fixture()
    cal=SessionCalendar(dict(coverage_start='2024-09-12',coverage_end='2024-09-20',
        sessions=[dict(date=d.date().isoformat(),open='09:30',close='16:00') for d in pd.bdate_range('2024-09-12','2024-09-20')]))
    rows=[make_candidate(r['provider'],r['kind'],dict(r['record'],record_date='2024-09-13',
        **{('pay_date' if r['provider']=='massive' else 'payable_date'):'2024-09-16'})) for r in rows]
    events,_,_=compile_ordinary_actions(rows,reviews,history,cal,ordinary_policy)
    policy=json.loads((Path(__file__).resolve().parents[1]/'docs/specs/V7_STOCK_CASH_LEDGER_ADMISSION_20260917.json').read_text())
    policy.update(eligible_existing_cash_events=1,sources={'fixture':'hash'})
    proposal=dict(schema='v7-stock-cash-ledger-reconstruction-proposal-v1',rules=policy['rules'],sources=policy['sources'],eligible_events=[dict(event_id=events[0]['action']['event_id'],security_id='security',symbol='ABC',ex_date='2024-09-13',record_date='2024-09-13',pay_date='2024-09-16')])
    return events,rows,cal,policy,proposal


def test_only_finite_authorized_dates_compile_and_cash_release_is_next_regular_open():
    args=compiled_inputs();events,pending=compile_cash_entitlements(*args)
    assert not pending and len(events)==1
    event=events[0]
    assert event['release_ns']==int(pd.Timestamp('2024-09-17T13:30Z').value)
    assert event['cash_per_share']=='0.44' and not event['broker_posting_verified']
    args[4]['eligible_events']=[];args[3]['eligible_existing_cash_events']=0
    assert compile_cash_entitlements(*args)[1][0]['reason']=='outside_authorized_finite_cash_set'


@pytest.mark.parametrize('change',['not_authorized','changed_rules','unknown_event','wrong_security','wrong_record',
    'conflicting_pay','due_bill','wrong_clock','duplicate_event'])
def test_cash_admission_rejects_changed_or_unreviewed_inputs(change):
    events,rows,cal,policy,proposal=deepcopy(compiled_inputs())
    if change=='not_authorized':policy['status']='pending'
    if change=='changed_rules':policy['rules']=[]
    if change=='unknown_event':proposal['eligible_events'][0]['event_id']='other'
    if change=='wrong_security':proposal['eligible_events'][0]['security_id']='other'
    if change=='wrong_record':rows[0]['record']['cash_amount']=999
    if change in ('conflicting_pay','due_bill'):
        field='pay_date' if change=='conflicting_pay' else 'due_bill_on_date'
        rows[0]['record'][field]='2024-09-12'
    if change=='wrong_clock':events[0]['action']['effective_at']='2024-09-13T14:30Z'
    if change=='duplicate_event':events*=2
    with pytest.raises(ValueError):compile_cash_entitlements(events,rows,cal,policy,proposal)


def event():
    return dict(schema='v7-stock-cash-entitlement-v1',event_id='cash-1',compiled_event_id='chart-1',
        security_id='SPY-id',symbol='SPY',policy_id=POLICY_ID,policy_identity='authorized-policy',
        source_identity='originals',cash_per_share='0.44',currency='USD',cash_units='per_listed_share_or_unit',
        ex_date='2024-05-28',record_date='2024-05-28',pay_date='2024-05-30',
        effective_ns=ns('2024-05-28','13:30'),available_ns=ns('2024-05-28','13:30'),
        release_ns=ns('2024-05-31','13:30'),withholding_fraction=0,dividend_fee_per_share=0,
        broker_posting_verified=False)


def purchase(book,quantity=10.,clock=None):
    fill=stock_fill(clock=clock or ns('2024-05-23','14:00'));fill['side']='buy'
    assert book.acquire_inventory('inventory','SPY','SPY-id',quantity,fill)


class Marks:
    def mark(self,symbol,clock):
        return dict(security_id='SPY-id',capture_identity='fixture-quote',sip_timestamp=clock,bid=110.)


def test_funded_unsettled_purchase_accrues_without_spendable_cash_and_releases_once():
    book=ledger();purchase(book,quantity=10.5);e=event()
    before=book.equity(e['effective_ns'],{},Marks());available=book.available_cash
    assert book.accrue_stock_cash(e,e['effective_ns'])==pytest.approx(4.62)
    assert book.cash==100000. and book.available_cash==available
    assert book.equity(e['effective_ns'],{},Marks())==pytest.approx(before+4.62)
    book.settle(ns('2024-05-29','13:30'));cash=book.cash;before=book.equity(e['release_ns'],{},Marks())
    assert book.release_stock_cash(e,e['release_ns'])==pytest.approx(4.62)
    assert book.cash==pytest.approx(cash+4.62) and not book.cash_receivables
    assert book.equity(e['release_ns'],{},Marks())==pytest.approx(before)
    assert book.release_stock_cash(e,e['release_ns'])==0
    assert book.reconcile()['cash_receivables']==0


def test_purchase_at_ex_open_has_no_entitlement_and_open_options_have_no_shares():
    e=event();book=ledger();purchase(book,clock=e['effective_ns']-1_000_000_000)
    assert book.accrue_stock_cash(e,e['effective_ns'])==0
    other=ledger();buy(other)
    assert other.accrue_stock_cash(e,e['effective_ns'])==0


def test_exercised_call_entitlement_survives_stock_sale_before_payment():
    book=ledger();contract=buy(book)
    assert book.expire('a',ns('2024-05-24','21:00'),**evidence(contract))=='exercise_committed'
    e=event();assert book.accrue_stock_cash(e,e['effective_ns'])==44.
    book.settle(ns('2024-05-30','13:30'));book.liquidate_stock('a',stock_fill())
    assert book.cash_receivables[e['event_id']]['amount']==44.
    cash=book.cash;book.release_stock_cash(e,e['release_ns'])
    assert book.cash==cash+44. and not book.cash_receivables
    assert book.reconcile()['cash_receivables']==0


def test_put_delivery_removes_only_delivered_funded_shares_before_ex_date():
    book=ledger();purchase(book,quantity=125.,clock=ns('2024-05-20','14:00'))
    book.settle(ns('2024-05-23','13:30'))
    contract=buy(book,right='P')
    assert book.expire('a',ns('2024-05-24','21:00'),**evidence(contract,90.))=='exercise_committed'
    e=event()
    assert book.accrue_stock_cash(e,e['effective_ns'])==11.
    book.settle(ns('2024-05-30','13:30'))
    assert book.release_stock_cash(e,e['release_ns'])==11.
    book.reconcile()


def test_sale_before_ex_open_cancels_entitlement_despite_unsettled_proceeds():
    book=ledger();contract=buy(book)
    book.expire('a',ns('2024-05-24','21:00'),**evidence(contract))
    book.settle(ns('2024-05-30','13:30'))
    book.liquidate_stock('a',stock_fill())
    e=event();e.update(ex_date='2024-05-31',record_date='2024-05-31',pay_date='2024-05-31',
        effective_ns=ns('2024-05-31','13:30'),available_ns=ns('2024-05-31','13:30'),
        release_ns=ns('2024-06-03','13:30'))
    assert book.accrue_stock_cash(e,e['effective_ns'])==0.
    assert not book.cash_receivables
    book.reconcile()


@pytest.mark.parametrize('change',['intraday_ex','intraday_release','later_release'])
def test_forged_calendar_clocks_rejected_before_ledger_mutation(change):
    book=ledger();purchase(book);e=event()
    if change=='intraday_ex':
        e['effective_ns']+=1_000_000_000;e['available_ns']=e['effective_ns']
    elif change=='intraday_release':e['release_ns']+=1_000_000_000
    else:e['release_ns']=ns('2024-06-03','13:30')
    before=deepcopy(book.__dict__)
    with pytest.raises(ValueError,match='regular opens'):book.accrue_stock_cash(e,e['effective_ns'])
    assert book.events==before['events'] and book.cash_receivables==before['cash_receivables']


def test_cash_payment_beyond_captured_settlement_coverage_remains_unresolved():
    book=ledger();purchase(book);e=event()
    book.settlement_calendar.document['coverage_end']='2024-05-30'
    with pytest.raises(ValueError,match='settlement coverage'):book.accrue_stock_cash(e,e['effective_ns'])
    assert not book.cash_receivables


@pytest.mark.parametrize('change',['early_accrual','late_accrual','early_release','unknown_release','duplicate_accrual','tax'])
def test_mistimed_or_unauthorized_cash_events_cannot_create_funds(change):
    book=ledger();purchase(book);e=event();clock=e['effective_ns']
    if change=='early_accrual':clock-=1
    if change=='late_accrual':clock+=1
    if change=='tax':e['withholding_fraction']=.1
    if change=='duplicate_accrual':book.accrue_stock_cash(e,clock)
    if change=='early_release':book.accrue_stock_cash(e,clock)
    before=deepcopy(book.__dict__)
    with pytest.raises(ValueError):
        if change=='early_release':book.release_stock_cash(e,e['release_ns']-1)
        elif change=='unknown_release':book.release_stock_cash(e,e['release_ns'])
        else:book.accrue_stock_cash(e,clock)
    for key in ('cash','cash_receivables','events','last_clock'):
        assert book.__dict__[key]==before[key]


def test_reconciliation_detects_corrupt_receivable_without_changing_cash():
    book=ledger();purchase(book);e=event();book.accrue_stock_cash(e,e['effective_ns'])
    book.cash_receivables[e['event_id']]['amount']+=1
    with pytest.raises(ValueError,match='receivable balance'):book.reconcile()


def test_portfolio_wires_cash_clocks_without_granting_cash_to_optionless_empty_portfolio():
    e=event();physical=SimpleNamespace(settlement_calendar=calendar(),policy=PhysicalPolicy(),stock_archive=None,cash_entitlements=[e])
    result=portfolio_replay([], [e['effective_ns']-1,e['effective_ns'],e['release_ns']],None,physical=physical)
    assert result['cash']==100000. and not result['physical_cash_receivables'] and result['complete']
    assert result['fills'][0]['kind']=='stock_cash_accrual' and result['fills'][0]['receivable']==0


def test_shared_portfolio_keeps_dividend_after_liquidation_and_waits_for_payment():
    class Options:
        def mark(self,contract,clock):
            return dict(bid=1.,ask=1.,price=1.,sip_timestamp=clock)
    class Stocks(Marks):
        def first_fill(self,symbol,clock,**kwargs):return stock_fill(symbol,clock)
    e=event();e.update(pay_date='2024-06-04',release_ns=ns('2024-06-05','13:30'))
    context=SimpleNamespace(settlement_calendar=calendar(),policy=PhysicalPolicy(),stock_archive=Stocks(),
        exercise_clock=lambda contract:ns('2024-05-24','21:00'),expiry_evidence=evidence,cash_entitlements=[e])
    decision=ns('2024-05-23','14:59');contract='SPY240524C00100000'
    proposal=dict(proposal_id='a',symbol='SPY',security_id='SPY-id',decision_ns=decision,score=1.,score_available_ns=decision,
        path=dict(proposal_id='a',capture_complete=True,label_complete=False,label_end_ns=None,
            fills=[dict(contract=contract,side='buy',price=1.,decision_ns=decision,sip_timestamp=decision+1_000_000_000)]))
    clocks=[decision,ns('2024-05-24','21:00'),e['effective_ns'],ns('2024-05-30','13:30'),ns('2024-06-03','13:30')]
    before=portfolio_replay([proposal],clocks,Options(),fraction=.001,physical=context,policy=QuotePolicy(fee=0.,slippage=0.))
    assert not before['active_proposals'] and not before['open_positions'] and not before['complete']
    assert before['physical_cash_receivables'][e['event_id']]['amount']==44.
    assert before['marks'][-1]['equity']==pytest.approx(before['cash']+44.)
    after=portfolio_replay([proposal],clocks+[e['release_ns']],Options(),fraction=.001,physical=context,policy=QuotePolicy(fee=0.,slippage=0.))
    assert after['complete'] and not after['physical_cash_receivables']
    assert after['cash']==pytest.approx(before['cash']+44.)
    assert after['marks'][-1]['equity']==pytest.approx(before['marks'][-1]['equity'])
