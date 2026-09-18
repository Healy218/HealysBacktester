"""Bind exact identity and primary-source relevance reviews for unrelated renames."""
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
    from nn_meta.v7.other_renames import unrelated_renames
    from nn_meta.v7.listed_evidence import ListedEvidence
    from nn_meta.v7.storage import verify,sha,identity,receipt,transaction
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('history','pending','other-instruments','listed-captures','calendar','reviews','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if (not args.output.resolve().is_relative_to(ROOT/'nn_meta') or shutil.disk_usage(ROOT).free<100*1024**3):
        raise ValueError('Repository artifact disk and reserve required')
    inputs={}
    def merge(values):
        for path,digest in values.items():
            if path in inputs and inputs[path]!=digest:raise ValueError('Conflicting source bindings')
            inputs[path]=digest
    def bind(path):
        doc=verify(path);merge({str(path/'complete.json'):sha(path/'complete.json')})
        merge({str(path/n):v for n,v in doc['files'].items()});return doc
    for path in (args.history,args.pending,args.other_instruments):
        bind(path);merge(json.loads((path/'inputs.json').read_text()))
    for path in [Path(__file__),args.calendar,args.reviews,ROOT/'nn_meta/session_calendar.py',
            *[ROOT/'nn_meta/v7'/(n+'.py') for n in ('other_renames','listed_evidence','daily_identities','cash_actions','storage','runtime')]]:
        merge({str(path):sha(path)})
    doc=json.loads(args.reviews.read_text())
    if doc.get('schema')!='v7-unrelated-rename-reviews-v1':raise ValueError('Finite relevance reviews required')
    pending=json.loads((args.pending/'unresolved.json').read_text());by_id={r['action_id']:r for r in pending}
    cal=SessionCalendar(json.loads(args.calendar.read_text()));sessions=sorted(cal.sessions)
    reader=ListedEvidence(args.listed_captures);listings={};reviews=[]
    for entry in doc['reviews']:
        review=dict(entry);evidence=review.pop('evidence')
        if not evidence:raise ValueError('Primary effective-date notice required')
        for e in evidence:
            path=Path(e['capture']);retained=bind(path)
            if (sha(path/'complete.json')!=e['receipt_sha256'] or retained['files']['response.bin']!=e['payload_sha256'] or not e['review']):
                raise ValueError('Primary evidence changed')
        review['evidence_identity']=identity(evidence)
        raw=by_id[review['record']['action_id']]['record'];day=review['effective_date'];prior=sessions[sessions.index(day)-1]
        witness=review['scoped_witness']
        for symbol,date in [(raw['old_symbol'],prior),(raw['new_symbol'],day),(witness['symbol'],witness['date'])]:
            listings[symbol,date]=reader.record(symbol,date)
        reviews.append(review)
    merge(reader.inputs)
    additions,pending=unrelated_renames(pending,reviews,listings,pd.read_parquet(args.history/'history.parquet'),cal)
    old=json.loads((args.other_instruments/'treatments.json').read_text());treatments=old+additions
    report=dict(new_unrelated_name_changes=len(additions),retained_unrelated_cash_groups=len(old),
        original_unrelated_records=sum(len(t['replaces']) for t in treatments),unresolved_original_records=len(pending),
        study_exclusions_added=0,research_ready=False)
    if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Review source changed')
    with transaction(args.output) as temp:
        for name,value in [('inputs',inputs),('report',report),('treatments',treatments),('unresolved',pending),('reviews',doc)]:
            (temp/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
        receipt(temp,dict(identity=identity(inputs),research_ready=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
