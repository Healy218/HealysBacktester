"""Compile retained whole-event reviews using exact active Alpaca prior closes."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import pandas as pd
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.cash_actions import compile_cash_actions
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('inventory','stock-daily','calendar','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--reviews',type=Path,action='append',required=True)
    args=parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta'):
        raise ValueError('Repository artifact disk required')
    inputs = {}

    def merge(bindings):
        for name,digest in bindings.items():
            if name in inputs and inputs[name] != digest:
                raise ValueError('Conflicting retained cash evidence bindings')
            inputs[name]=digest

    def bind(path):
        document=verify(path)
        merge({str(path/'complete.json'):sha(path/'complete.json')})
        merge({str(path/name):digest for name,digest in document['files'].items()})
        return document

    bind(args.inventory)
    declaration=json.loads((args.inventory/'declaration.json').read_text())
    merge(declaration['inputs']);merge(declaration['sources'])
    summary=args.stock_daily/'summary'
    bind(summary)
    daily_binding=json.loads((summary/'binding.json').read_text())
    merge(daily_binding['declaration']['inputs'])
    merge(daily_binding['declaration']['sources'])
    reviews=[]
    for path in args.reviews:
        document=bind(path)
        if document.get('schema') != 'v7-cash-reviews-v1':
            raise ValueError('Explicit sealed cash-event reviews required')
        merge(json.loads((path/'inputs.json').read_text()))
        reviews.extend(json.loads((path/'cash_reviews.json').read_text()))
    sources=[Path(__file__),ROOT/'nn_meta/v7/cash_actions.py',ROOT/'nn_meta/v7/causal_prices.py',
             ROOT/'nn_meta/v7/action_inventory.py',ROOT/'nn_meta/v7/storage.py',ROOT/'nn_meta/session_calendar.py']
    for path in [args.calendar,*sources]:
        merge({str(path):sha(path)})
    if any(sha(p)!=digest for p,digest in inputs.items()):
        raise ValueError('Cash review inputs differ from verified parents')
    candidates=json.loads((args.inventory/'candidates.json').read_text())
    stock=pd.read_parquet(summary/'eligible_daily.parquet')
    calendar=SessionCalendar(json.loads(args.calendar.read_text()))
    events,unresolved=compile_cash_actions(candidates,reviews,stock,calendar)
    report=dict(candidate_records=len(candidates),compiled_events=len(events),
        consumed_provider_records=sum(len(e['replaces']) for e in events),
        unresolved_provider_records=len(unresolved),
        reviewed_event_securities=len({e['security_id'] for e in events}),
        full_security_admitted=False,research_ready=False,
        limitations=['Only explicitly reviewed whole cash groups are compiled',
                     'Full action/no-event coverage and security continuity remain required'])
    if report['consumed_provider_records']+len(unresolved)!=len(candidates):
        raise ValueError('Cash event accounting does not partition inventory')
    if any(sha(p)!=digest for p,digest in inputs.items()):
        raise ValueError('Cash evidence changed during calculation')
    with transaction(args.output) as temp:
        for name,value in [('report',report),('inputs',inputs),('actions',events),
                           ('unresolved',unresolved),('reviews',reviews)]:
            (temp/(name+'.json')).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
        receipt(temp,dict(identity=identity(inputs),research_ready=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
