"""Add exact primary-reviewed common-share cash events to retained action inputs."""
from pathlib import Path
import argparse
import json
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.reviewed_cash import compile_reviewed_cash
    from nn_meta.v7.storage import identity,sha,verify,transaction,receipt
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('actions','inventory','history','calendar','reviews','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta') or shutil.disk_usage(ROOT).free<100*1024**3:
        raise ValueError('Repository artifact disk and reserve required')
    inputs={}
    def merge(values):
        for p,d in values.items():
            if p in inputs and inputs[p]!=d:raise ValueError('Conflicting cash source bindings')
            inputs[p]=d
    def bind(path):
        doc=verify(path);merge({str(path/'complete.json'):sha(path/'complete.json')})
        merge({str(path/n):d for n,d in doc['files'].items()});return doc
    for p in (args.actions,args.history):
        bind(p);merge(json.loads((p/'inputs.json').read_text()))
    bind(args.inventory)
    declaration=json.loads((args.inventory/'declaration.json').read_text())
    merge(declaration['inputs']);merge(declaration['sources'])
    for p in [Path(__file__),args.reviews,args.calendar,ROOT/'nn_meta/session_calendar.py',
              *[ROOT/'nn_meta/v7'/(n+'.py') for n in ('reviewed_cash','action_inventory','cash_actions','causal_prices','storage','runtime')]]:
        merge({str(p):sha(p)})
    document=json.loads(args.reviews.read_text())
    if document['schema']!='v7-finite-primary-cash-reviews-v1':raise ValueError('Finite exact cash reviews required')
    reviews=[]
    for original in document['reviews']:
        review=dict(original);evidence=review.pop('evidence')
        if not evidence:raise ValueError('Primary cash notice required')
        for e in evidence:
            p=Path(e['capture']);doc=bind(p)
            if (sha(p/'complete.json')!=e['receipt_sha256'] or doc['files'].get('response.bin')!=e['payload_sha256']
                    or not e['review']):raise ValueError('Reviewed primary source differs')
        review['evidence_identity']=identity(evidence)
        review['publication_available_at']=max(pd.Timestamp(e['publication_available_at']) for e in evidence).isoformat()
        reviews.append(review)
    new,pending=compile_reviewed_cash(json.loads((args.actions/'unresolved.json').read_text()),reviews,
        pd.read_parquet(args.history/'history.parquet'),SessionCalendar(json.loads(args.calendar.read_text())))
    base=json.loads((args.actions/'actions.json').read_text());events=base+new
    clocks=[(e['security_id'],e['action']['effective_at']) for e in events]
    if len(set(clocks))!=len(clocks):raise ValueError('Simultaneous actions require combined review')
    original_count=len(json.loads((args.inventory/'candidates.json').read_text()))
    if sum(len(e['replaces']) for e in events)+len(pending)!=original_count:
        raise ValueError('Cash reviews must preserve the original record partition')
    report=dict(compiled_events=len(events),preserved_existing_events=len(base),reviewed_cash_events=len(new),
        unresolved_provider_records=len(pending),held_history_admitted=False,research_ready=False)
    if any(sha(p)!=d for p,d in inputs.items()):raise ValueError('Cash source changed')
    with transaction(args.output) as temp:
        for name,value in [('inputs',inputs),('report',report),('actions',events),('unresolved',pending),('reviews',document)]:
            (temp/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
        receipt(temp,dict(identity=identity(inputs),research_ready=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
