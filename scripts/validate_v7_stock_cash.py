"""Verify the finite cash-event census and a captured funded AAPL entitlement.

This is a bounded accounting verification, not a completed strategy replay.
Only the reviewed 2022 settlement year is normalized here.
"""
from pathlib import Path
import argparse
from decimal import Decimal
import json
import math
import shutil
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.physical import PhysicalLedger,PhysicalPolicy,SettlementCalendar
    from nn_meta.v7.portfolio import portfolio_replay
    from nn_meta.v7.stock_cash import validate_cash_event,validate_policy
    from nn_meta.v7.stock_quotes import StockQuoteArchive
    from nn_meta.v7.storage import identity,sha,verify,receipt,transaction
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('events','actions','calendar','quotes','settlement-review','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta') or shutil.disk_usage(ROOT).free<100*1024**3:
        raise ValueError('Repository artifact disk and reserve required')
    inputs={}
    def merge(values):
        for p,d in values.items():
            if p in inputs and inputs[p]!=d:raise ValueError('Conflicting verification inputs')
            inputs[p]=d
    def bind(path):
        doc=verify(path)
        merge({str(path/'complete.json'):sha(path/'complete.json')})
        merge({str(path/n):d for n,d in doc['files'].items()})
        return doc
    bind(args.events);bind(args.actions);quote=bind(args.quotes);bind(args.calendar.parent)
    merge(json.loads((args.events/'inputs.json').read_text()))
    merge(quote['capture']['evidence'])
    for p in [Path(__file__),args.settlement_review,ROOT/'nn_meta/session_calendar.py',
              ROOT/'options/data/provider.py',*[ROOT/'nn_meta/v7'/(n+'.py') for n in
              ('physical','portfolio','execution','stock_quotes','stock_cash','storage','runtime')]]:
        merge({str(p):sha(p)})
    if str(args.calendar) not in inputs:raise ValueError('Cash events must bind this trading calendar')
    review=json.loads(args.settlement_review.read_text());source=Path(review['source']);bind(source)
    if (review['schema']!='v7-reviewed-settlement-year-v1' or review['year']!=2022
            or review['coverage_start']!='2022-01-01' or review['coverage_end']!='2022-12-31'
            or sha(source/'complete.json')!=review['source_receipt_sha256']
            or sha(source/'response.bin')!=review['source_document_sha256']
            or len(review['checked_trade_settlement_pairs'])!=46):
        raise ValueError('Exact visually reviewed 2022 annual settlement notice required')
    trading=SessionCalendar(json.loads(args.calendar.read_text()))
    days=[d.date().isoformat() for d in pd.bdate_range(review['coverage_start'],review['coverage_end'])
          if d.date().isoformat() not in review['settlement_holidays']]
    expected={d for d in trading.sessions if review['coverage_start']<=d<=review['coverage_end']}
    expected-=set(review['trading_bank_holidays'])
    expected.update(review['settlement_open_trading_closed'])
    if set(days)!=expected:raise ValueError('Unreviewed trading/settlement calendar difference')
    document=dict(schema='v7-settlement-calendar-v1',business_dates=days,
        coverage_start=review['coverage_start'],coverage_end=review['coverage_end'],
        source_identity=identity(review),available_ns=review['available_ns'],review_path=str(args.settlement_review),
        source_receipt_sha256=review['source_receipt_sha256'],research_ready=False)
    settlement=SettlementCalendar(document,trading)
    for row in review['checked_trade_settlement_pairs']:
        clock=int(trading.bounds(row['trade_date'])[0].tz_localize('UTC').value)
        if settlement.settlement(clock)[0]!=row['settlement_date']:
            raise ValueError('Calendar differs from original FINRA trade/settlement table')
    policy=json.loads((args.events/'policy.json').read_text())
    proposal=json.loads(Path(policy['proposal_path']).read_text())
    if sha(policy['proposal_path'])!=policy['proposal_sha256']:raise ValueError('Authorized proposal changed')
    policy_id=validate_policy(policy,proposal)
    events=json.loads((args.events/'events.json').read_text())
    approved={e['event_id']:e for e in proposal['eligible_events']}
    originals={e['action']['event_id']:e for e in json.loads((args.actions/'actions.json').read_text())}
    if len(events)!=len(approved) or {e['compiled_event_id'] for e in events}!=set(approved):
        raise ValueError('Full finite authorized cash census required')
    opens=pd.DatetimeIndex([trading.bounds(d)[0].tz_localize('UTC') for d in sorted(trading.sessions)])
    for e in events:
        validate_cash_event(e,trading)
        original=originals[e['compiled_event_id']];a=approved[e['compiled_event_id']]
        next_midnight=(pd.Timestamp(e['pay_date'],tz='America/New_York')+pd.DateOffset(days=1)).tz_convert('UTC')
        expected_release=int(opens[opens.searchsorted(next_midnight)].value)
        if (e['release_ns']!=expected_release or e['source_identity']!=identity(original)
                or e['policy_identity']!=policy_id or e['replaces']!=original['replaces']
                or e['event_id']!='stock-cash:'+identity({k:v for k,v in e.items() if k!='event_id'})
                or Decimal(e['cash_per_share'])!=Decimal(str(original['cash_amount']))
                or any(e[k]!=a[k] for k in ('security_id','symbol','ex_date','record_date','pay_date'))):
            raise ValueError('Compiled cash census differs from approved original or independent clock calculation')
    # Only the reviewed settlement year can enter the actual ledger consumer.
    year_events=[e for e in events if e['ex_date'][:4]=='2022'
                 and pd.Timestamp(e['release_ns'],unit='ns',tz='UTC').year==2022]
    clocks=sorted({e[k] for e in year_events for k in ('effective_ns','release_ns')})
    context=SimpleNamespace(settlement_calendar=settlement,policy=PhysicalPolicy(),stock_archive=None,
                            cash_entitlements=year_events)
    empty=portfolio_replay([],clocks,None,physical=context)
    if (not empty['complete'] or empty['cash']!=100000. or len(empty['fills'])!=len(year_events)
            or any(e['receivable'] for e in empty['fills'])):
        raise ValueError('Actual cash events created money without funded beneficial shares')
    # Reuse the original AAPL quote archive; do not substitute a close or invent a later mark.
    archive=StockQuoteArchive([args.quotes],calendar=trading)
    case=[e for e in events if e['symbol']=='AAPL' and e['ex_date']=='2022-05-06']
    if len(case)!=1:raise ValueError('Exact existing AAPL cash case required')
    e=case[0];decision=quote['capture']['start_ns']
    fill=archive.first_fill('AAPL',decision,side='buy',quantity=100.)
    book=PhysicalLedger(settlement_calendar=settlement)
    if fill is None or not book.acquire_inventory('aapl-funded','AAPL',e['security_id'],100.,fill):
        raise ValueError('Existing captured quote must fund 100 actual simulated shares')
    commitment=dict(book.commitments['aapl-funded']);available=book.available_cash
    expected=float(Decimal(e['cash_per_share'])*100)
    if book.accrue_stock_cash(e,e['effective_ns'])!=expected or book.available_cash!=available:
        raise ValueError('Dividend must accrue without releasing spendable cash')
    if book.reserve_entry('cannot-spend-dividend',available+expected):
        raise ValueError('Dividend receivable incorrectly funded an entry')
    book.settle(commitment['available_ns']);before=book.cash
    if (book.shares!= {('AAPL',e['security_id']):100.}
            or book.release_stock_cash(e,e['release_ns'])!=expected
            or not math.isclose(book.cash,before+expected,abs_tol=1e-8)
            or book.release_stock_cash(e,e['release_ns'])!=0):
        raise ValueError('Stock funding and cash release do not reconcile')
    reconciliation=book.reconcile()
    report=dict(schema='v7-stock-cash-verification-v1',verified_cash_events=len(events),
        securities=len({e['security_id'] for e in events}),settlement_year=2022,
        settlement_business_dates=len(days),original_settlement_table_checks=46,
        no_inventory_portfolio_events=len(year_events),no_inventory_portfolio_cash=empty['cash'],
        captured_funded_case=dict(symbol='AAPL',shares=100,fill=fill,cash_event=e,
            stock_settlement=commitment,receivable=expected,cash_before_dividend_release=before,
            cash_after_dividend_release=book.cash,reconciliation=reconciliation),
        limits=['Accounting case retains 100 funded shares; no stock liquidation or completed strategy outcome.',
                'No equity marks beyond the existing quote window; no fabricated held mark.',
                '2023-2026 settlement calendars remain unadmitted; 55 other compiled cash events remain outside policy.'],
        held_history_admitted=False,research_ready=False,broker_posting_verified=False)
    if any(sha(p)!=d for p,d in inputs.items()):raise ValueError('Cash verification source changed')
    with transaction(args.output) as temp:
        for name,value in [('inputs',inputs),('report',report),('settlement_calendar',document),
                           ('funded_ledger',book.events),('no_inventory_portfolio',empty)]:
            (temp/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
        receipt(temp,dict(identity=identity(inputs),research_ready=False))
    print(json.dumps({k:v for k,v in report.items() if k!='captured_funded_case'},indent=2))


if __name__=='__main__':main()
