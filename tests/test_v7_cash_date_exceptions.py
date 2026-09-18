from copy import deepcopy
from pathlib import Path
import json

import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.action_inventory import candidate
from nn_meta.v7.cash_date_exceptions import NASDAQ_NOTICE_SHA
from nn_meta.v7.ordinary_actions import compile_ordinary_actions
from nn_meta.v7.physical import PhysicalLedger, SettlementCalendar
from nn_meta.v7.stock_cash import POLICY_ID, validate_cash_event
from nn_meta.v7.stock_cash_dates import compile_date_reviewed_cash
from nn_meta.v7.storage import identity
from nn_meta.v7.producer_versions import ROOT, SNAPSHOTS, historical_input_bindings
from tests.test_v7_physical import stock_fill


def case():
    days = [d.date().isoformat() for d in pd.bdate_range('2025-01-07', '2025-01-24')]
    cal = SessionCalendar(dict(coverage_start=days[0], coverage_end=days[-1], sessions=[
        dict(date=d, open='09:30', close='16:00') for d in days if d not in ('2025-01-09','2025-01-20')]))
    originals = [('massive', 'dividends', dict(id='m', ticker='INTU', ex_dividend_date='2025-01-10',
        currency='USD', cash_amount=1.04, record_date='2025-01-09', pay_date='2025-01-17')),
        ('alpaca','cash_dividends',dict(id='a',symbol='INTU',ex_date='2025-01-10',foreign=False,
            rate=1.04,record_date='2025-01-09',payable_date='2025-01-17'))]
    rows = [candidate(p,k,r,scoped_symbols={'INTU'},start=cal.start,end=cal.end,
        source={'receipt':'fixture'}) for p,k,r in originals]
    history = pd.DataFrame([dict(stock_ticker='INTU', source_date=d, security_id='sid',
        identity_span='span', raw_close=c, observed_minutes=390,
        session_open_ns=cal.bounds(d)[0].tz_localize('UTC').value,
        available_ns=cal.bounds(d)[1].tz_localize('UTC').value) for d,c in
        [('2025-01-08',100.),('2025-01-10',98.96)]])
    ordinary = json.loads((ROOT/'docs/specs/V7_ORDINARY_ACTION_ADMISSION_20260917.json').read_text())
    actions, pending, _ = compile_ordinary_actions(rows, [], history, cal, ordinary)
    assert len(actions)==1 and not pending
    source=actions[0]
    proposal=dict(eligible_groups=[dict(symbol='INTU',ex_date='2025-01-10',replaces=source['replaces'])])
    policy=dict(schema='v7-remaining-stock-cash-extension-admission-v1', status='user_authorized',
        authorization='Fixture authorization', proposal_identity=identity(proposal),model_policy_id=POLICY_ID)
    review=dict(schema='v7-primary-cash-date-review-v1',compiled_event_id=source['action']['event_id'],
        compiled_source_identity=identity(source),symbol='INTU',security_id='sid',cash_per_share='1.04',
        ex_date='2025-01-10',record_date='2025-01-09',pay_date='2025-01-17',
        conclusion='ordinary_cash_dates_resolved',publication_time_used_for_chart=False,
        rationale='Issuer dates plus exchange closure notice',evidence_identity='issuer-and-exchange',
        replaces=source['replaces'],record_date_exception=dict(schema='v7-nasdaq-eta2025-1-cash-dates-v1',
            notice_payload_sha256=NASDAQ_NOTICE_SHA))
    return [actions,rows,[],cal,policy,proposal],review,days


def test_closed_record_date_preserved_through_funded_ledger_and_release():
    args, review, days=case(); before=deepcopy(args[0])
    e=compile_date_reviewed_cash(*args,[review])[0];cal=args[3]
    assert e['record_date']=='2025-01-09' and args[0]==before
    settlement=SettlementCalendar(dict(schema='v7-settlement-calendar-v1',source_identity='fixture',
        coverage_start=days[0],coverage_end=days[-1],business_dates=[d for d in days if d!='2025-01-20']),cal)
    book=PhysicalLedger(settlement_calendar=settlement)
    fill=stock_fill('INTU',clock=cal.bounds('2025-01-08')[0].tz_localize('UTC').value)
    fill.update(side='buy',security_id='sid')
    assert book.acquire_inventory('funded','INTU','sid',10.,fill)
    available=book.available_cash
    assert book.accrue_stock_cash(e,e['effective_ns'])==pytest.approx(10.4)
    assert book.available_cash==available and book.cash_receivables[e['event_id']]['amount']==10.4
    book.settle(e['effective_ns']);cash=book.cash
    assert e['release_ns']==cal.bounds('2025-01-21')[0].tz_localize('UTC').value
    assert book.release_stock_cash(e,e['release_ns'])==10.4
    assert book.cash==pytest.approx(cash+10.4) and not book.cash_receivables
    assert book.release_stock_cash(e,e['release_ns'])==0
    book.reconcile()


@pytest.mark.parametrize('change',['missing_notice','wrong_notice','other_date','other_symbol','open_record','no_calendar'])
def test_exception_cannot_waive_arbitrary_chronology(change):
    args,review,_=case();e=compile_date_reviewed_cash(*args,[review])[0];cal=args[3]
    if change=='missing_notice':e.pop('record_date_exception')
    if change=='wrong_notice':e['record_date_exception']['notice_payload_sha256']='different'
    if change=='other_date':e['record_date']='2025-01-08'
    if change=='other_symbol':e['symbol']='OTHER'
    if change=='open_record':
        cal=SessionCalendar(dict(coverage_start='2025-01-07',coverage_end='2025-01-24',sessions=[
            dict(date=d,open='09:30',close='16:00') for d in ['2025-01-08','2025-01-09','2025-01-10','2025-01-17','2025-01-21']]))
    if change=='no_calendar':cal=None
    with pytest.raises(ValueError):validate_cash_event(e,cal)


def test_historical_producer_snapshots_match_exact_original_hashes():
    values={str(ROOT/p):d for p,d in SNAPSHOTS}
    bound=historical_input_bindings(values)
    assert set(bound)=={str(ROOT/p) for p in SNAPSHOTS.values()}
    assert values=={str(ROOT/p):d for p,d in SNAPSHOTS}
    with pytest.raises(ValueError):historical_input_bindings({str(ROOT/'nn_meta/v7/stock_cash.py'):'unknown'})
