from copy import deepcopy
from decimal import Decimal

import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.dividend_resolution import compile_dividend_resolutions, BASIS
from nn_meta.v7.dividend_components import validate_components
from nn_meta.v7.ordinary_actions import price_action
from nn_meta.v7.causal_daily import returns
from nn_meta.v7.stock_cash import POLICY_ID
from nn_meta.v7.storage import identity
from tests.test_v7_reviewed_cash import fixture


def case():
    rows, old_reviews, history, _ = fixture()
    calendar = SessionCalendar(dict(coverage_start='2024-06-11', coverage_end='2024-06-17',
        sessions=[dict(date=d, open='09:30', close='16:00') for d in
                  ['2024-06-11','2024-06-12','2024-06-13','2024-06-14','2024-06-17']]))
    history['session_open_ns'] = [calendar.bounds(d)[0].tz_localize('UTC').value for d in history.source_date]
    evidence = [dict(capture='fixture-primary', receipt_sha256='fixture',payload_sha256='fixture')]
    review = dict(schema='v7-primary-dividend-resolution-v1',symbol='ABC',ex_date='2024-06-12',
        security_id='sid',currency='USD',cash_units='per_listed_share_or_unit',cash_per_share='.15',
        publication_verified=False,evidence=evidence,evidence_identity=identity(evidence),
        rationale='Fixture primary total with two different payment clocks.',
        replaces=old_reviews[0]['replaces'], payments=[
            dict(name='base',cash_per_share='.075',record_date='2024-06-12',pay_date='2024-06-12',terms_evidence_identity=identity(evidence[0])),
            dict(name='variable',cash_per_share='.075',record_date='2024-06-12',pay_date='2024-06-14',terms_evidence_identity=identity(evidence[0]))])
    proposal=dict(eligible_groups=[dict(replaces=deepcopy(review['replaces']))])
    policy=dict(schema='v7-dividend-resolution-policy-v1',status='user_authorized',scope_change=False,
        currency='USD',model_policy_id=POLICY_ID,publication_verified=False,require_primary_terms=True,
        withholdings_and_fees_modeled=False,preserve_original_records=True,authorization='Fixture',
        proposal_identity=identity(proposal))
    return rows,[review],history,calendar,policy,proposal


def test_one_price_adjustment_and_separate_payments_reconcile():
    args=case();original=deepcopy(args[0])
    actions,cash,pending=compile_dividend_resolutions(*args)
    assert not pending and args[0]==original and len(actions)==1 and len(cash)==2
    assert price_action(actions[0]).admission_basis==BASIS
    assert cash[0]['compiled_event_id']==cash[1]['compiled_event_id']
    assert cash[0]['event_id']!=cash[1]['event_id']
    assert cash[0]['release_ns']<cash[1]['release_ns']
    assert sum(Decimal(e['cash_per_share']) for e in cash)==Decimal('.15')
    assert len(validate_components(actions,cash,args[3]))==1
    result=returns(args[2],[price_action(actions[0])],args[3],security_id='sid',
        start='2024-06-11',end='2024-06-12',action_evidence_identity='fixture')
    assert result.simple_return.iloc[-1]==pytest.approx(0)


@pytest.mark.parametrize('change',['partial','duplicate','source','unapproved','scope','total','name',
    'evidence','component_evidence','publication','currency','sid','span','prior','date','duebill'])
def test_unresolved_or_changed_terms_cannot_compile(change):
    args=list(case());r=args[1][0]
    if change=='partial':r['replaces'].pop()
    if change=='duplicate':args[1].append(deepcopy(r))
    if change=='source':args[0][0]['record']['cash_amount']=9
    if change=='unapproved':args[4]['status']='proposed'
    if change=='scope':args[5]['eligible_groups']=[]
    if change=='total':r['cash_per_share']='.075'
    if change=='name':r['payments'][1]['name']='base'
    if change=='evidence':r['evidence'][0]['payload_sha256']='changed'
    if change=='component_evidence':r['payments'][0]['terms_evidence_identity']='changed'
    if change=='publication':r['publication_verified']=True
    if change=='currency':r['currency']='CAD'
    if change=='sid':r['security_id']='other'
    if change=='span':args[2].loc[0,'identity_span']='other'
    if change=='prior':args[2]=args[2].iloc[1:]
    if change=='date':r['payments'][0]['record_date']='2024-06-11'
    if change=='duebill':
        args[0][0]['record']['due_bill_on_date']='2024-06-12'
        args[0][0]['record_sha256']=identity(args[0][0]['record'])
        r['replaces'][0]['record_sha256']=args[0][0]['record_sha256']
        args[5]['eligible_groups'][0]['replaces']=deepcopy(r['replaces'])
        args[4]['proposal_identity']=identity(args[5])
    with pytest.raises(ValueError):compile_dividend_resolutions(*args)


@pytest.mark.parametrize('change',['missing','duplicate','amount','pay','index','source','count'])
def test_payment_partition_cannot_hide_missing_or_duplicate_cash(change):
    args=case();actions,cash,_=compile_dividend_resolutions(*args)
    if change=='missing':cash.pop()
    if change=='duplicate':cash.append(deepcopy(cash[0]))
    if change=='amount':cash[0]['cash_per_share']='.15'
    if change=='pay':cash[0]['pay_date']='2024-06-13'
    if change=='index':cash[1]['dividend_component_index']=0
    if change=='source':cash[0]['source_identity']='changed'
    if change=='count':cash[0]['dividend_component_count']=1
    for e in cash:e['event_id']='stock-cash:'+identity({k:v for k,v in e.items() if k!='event_id'})
    with pytest.raises(ValueError):validate_components(actions,cash,args[3])


def test_funded_components_accrue_once_and_release_on_independent_clocks():
    from nn_meta.v7.physical import PhysicalLedger, SettlementCalendar
    from nn_meta.v7.execution import QuotePolicy
    from tests.test_v7_physical import stock_fill, ns
    args=case();_,cash,_=compile_dividend_resolutions(*args);trading=args[3]
    schedule=SettlementCalendar(dict(schema='v7-settlement-calendar-v1',
        business_dates=sorted(trading.sessions),coverage_start=trading.start,coverage_end=trading.end,
        source_identity='fixture-settlement'),trading)
    book=PhysicalLedger(capital=100000.,settlement_calendar=schedule,policy=QuotePolicy(fee=0.,slippage=0.))
    fill=stock_fill('ABC',ns('2024-06-11','14:00'))
    fill.update(side='buy',security_id='sid')
    assert book.acquire_inventory('funded','ABC','sid',10,fill)
    available=book.available_cash
    for e in cash:assert book.accrue_stock_cash(e,e['effective_ns'])==pytest.approx(.75)
    assert book.available_cash==available
    assert book.reconcile()['cash_receivables']==pytest.approx(1.5)
    book.settle(cash[0]['release_ns']);before=book.cash
    assert book.release_stock_cash(cash[0],cash[0]['release_ns'])==pytest.approx(.75)
    assert book.cash==pytest.approx(before+.75)
    assert book.reconcile()['cash_receivables']==pytest.approx(.75)
    assert book.release_stock_cash(cash[0],cash[0]['release_ns'])==0
    assert book.release_stock_cash(cash[1],cash[1]['release_ns'])==pytest.approx(.75)
    assert book.cash==pytest.approx(before+1.5) and not book.cash_receivables
