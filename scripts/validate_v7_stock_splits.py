"""Verify a funded TSLA holding across its reviewed 2022 split with raw quotes."""
from pathlib import Path
import argparse
import json
import math
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.physical import PhysicalLedger,SettlementCalendar
    from nn_meta.v7.stock_splits import stock_split_terms
    from nn_meta.v7.stock_quotes import StockQuoteArchive
    from nn_meta.v7.storage import identity,sha,verify,receipt,transaction
    parser=argparse.ArgumentParser(description=__doc__)
    for n in ('actions','quotes','cash-verification','calendar','output'):
        parser.add_argument('--'+n,type=Path,required=True)
    args=parser.parse_args();inputs={}
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta') or shutil.disk_usage(ROOT).free<100*1024**3:
        raise ValueError('Repository artifact disk and reserve required')
    def merge(values):
        for p,d in values.items():
            if p in inputs and inputs[p]!=d:raise ValueError('Conflicting source bindings')
            inputs[p]=d
    def bind(path):
        d=verify(path);merge({str(path/'complete.json'):sha(path/'complete.json')})
        merge({str(path/n):h for n,h in d['files'].items()});return d
    for p in (args.actions,args.cash_verification):
        bind(p);merge(json.loads((p/'inputs.json').read_text()))
    bind(args.calendar.parent)
    paths=sorted(p.parent for p in args.quotes.glob('*/complete.json'))
    if len(paths)!=2:raise ValueError('Exact two-window stock quote capture required')
    captures=[bind(p) for p in paths]
    for d in captures:merge(d['capture']['evidence'])
    for p in [Path(__file__),ROOT/'nn_meta/session_calendar.py',ROOT/'options/data/provider.py',
              ROOT/'options/data/massive_ticks.py',*[ROOT/'nn_meta/v7'/(n+'.py') for n in
              ('physical','stock_splits','ordinary_actions','causal_prices','action_inventory',
               'stock_quotes','execution','stock_cash','storage','runtime')]]:
        merge({str(p):sha(p)})
    if any(sha(p)!=d for p,d in inputs.items()):raise ValueError('Split consumer source changed')
    cal=SessionCalendar(json.loads(args.calendar.read_text()))
    settlement=SettlementCalendar(json.loads((args.cash_verification/'settlement_calendar.json').read_text()),cal)
    selected=[e for e in json.loads((args.actions/'actions.json').read_text())
        if e['symbol']=='TSLA' and e['effective_date']=='2022-08-25']
    if len(selected)!=1:raise ValueError('Exact compiled TSLA split required')
    event=selected[0];_,clock,ratio=stock_split_terms(event,cal)
    assert ratio==3 and event['security_id']=='BBG000N9MNX3'
    archive=StockQuoteArchive(paths,calendar=cal)
    decision=int(cal.bounds('2022-08-22')[0].tz_localize('UTC').value)
    fill=archive.first_fill('TSLA',decision,side='buy',quantity=10.)
    book=PhysicalLedger(settlement_calendar=settlement)
    if fill is None or not book.acquire_inventory('funded-tsla','TSLA',event['security_id'],10.,fill):
        raise ValueError('Observed funded pre-split purchase required')
    commitment=dict(book.commitments['funded-tsla']);available=book.available_cash
    assert commitment['settled_on']=='2022-08-24' and commitment['available_ns']==clock
    assert book.apply_stock_split(event,clock)==20.
    assert book.available_cash==available and book.cash==100000.
    assert book.commitments['funded-tsla']['cash_delta']==commitment['cash_delta']
    book.settle(clock)
    assert book.shares=={('TSLA',event['security_id']):30.}
    assert math.isclose(book.cash,available,abs_tol=1e-8)
    mark_clock=clock+60_000_000_000;mark=archive.mark('TSLA',mark_clock)
    equity=book.equity(mark_clock,{},archive)
    assert math.isclose(equity,book.cash+30*mark['bid'],abs_tol=1e-8)
    report=dict(schema='v7-funded-stock-split-verification-v1',symbol='TSLA',event_id=event['action']['event_id'],
        funded_purchase=fill,stock_settlement=commitment,old_shares=10,new_shares=30,
        cash=book.cash,available_cash=book.available_cash,mark_clock=mark_clock,observed_mark=mark,equity=equity,
        reconciliation=book.reconcile(),held_history_admitted=False,research_ready=False,
        limitations=['Bounded accounting and observed mark case; retains funded stock, no liquidation or strategy verdict.',
            'Open option adjustments require separate exact contract evidence.',
            'Only the reviewed 2022 settlement calendar is used.'])
    if any(sha(p)!=d for p,d in inputs.items()):raise ValueError('Split source changed during verification')
    with transaction(args.output) as temp:
        for n,v in [('inputs',inputs),('report',report),('ledger',book.events)]:
            (temp/(n+'.json')).write_text(json.dumps(v,indent=2)+'\n')
        receipt(temp,dict(identity=identity(inputs),research_ready=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
