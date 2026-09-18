"""Seal finite primary-notice and exact-listing common-share rename reviews."""
from pathlib import Path
import argparse
import json
import shutil
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.listed_evidence import ListedEvidence
    from nn_meta.v7.renames import compile_renames
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('history','pending','listed-captures','calendar','reviews','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    if (not args.output.resolve().is_relative_to(ROOT/'nn_meta')
            or shutil.disk_usage(ROOT).free < 100*1024**3):
        raise ValueError('Repository artifact disk and reserve required')
    inputs = {}
    def merge(values):
        for name, digest in values.items():
            if name in inputs and inputs[name] != digest:
                raise ValueError('Conflicting source bindings')
            inputs[name] = digest
    def bind(path):
        doc = verify(path)
        merge({str(path/'complete.json'):sha(path/'complete.json')})
        merge({str(path/n):h for n,h in doc['files'].items()})
        return doc
    for path in (args.history,args.pending):
        bind(path); merge(json.loads((path/'inputs.json').read_text()))
    for path in [Path(__file__),args.calendar,args.reviews,ROOT/'nn_meta/session_calendar.py',
                 *[ROOT/'nn_meta/v7'/(n+'.py') for n in ('renames','listed_evidence','daily_identities','cash_actions','storage','runtime')]]:
        merge({str(path):sha(path)})
    doc=json.loads(args.reviews.read_text())
    if doc.get('schema') != 'v7-finite-common-share-rename-reviews-v1':
        raise ValueError('Finite common-share rename reviews required')
    cal=SessionCalendar(json.loads(args.calendar.read_text())); sessions=sorted(cal.sessions)
    reader=ListedEvidence(args.listed_captures); listings={}
    pending=json.loads((args.pending/'unresolved.json').read_text())
    by_id={r['action_id']:r for r in pending}
    reviews=[]
    for original in doc['reviews']:
        review=dict(original); evidence=review.pop('evidence')
        if not evidence:
            raise ValueError('Primary publication evidence required')
        for e in evidence:
            path=Path(e['capture']); retained=bind(path)
            if (sha(path/'complete.json')!=e['receipt_sha256']
                    or retained['files'].get('response.bin')!=e['payload_sha256']
                    or not e['review']):
                raise ValueError('Primary evidence receipt differs')
        review['evidence_identity']=identity(evidence)
        clocks=[pd.Timestamp(e['publication_available_at']) for e in evidence]
        if any(pd.isna(t) or t.tzinfo is None for t in clocks):
            raise ValueError('Conservative timezone-aware publication clock required')
        review['publication_available_ns']=max(int(t.value) for t in clocks)
        raw=by_id[review['record']['action_id']]['record']
        day=review['effective_date']; prior=sessions[sessions.index(day)-1]
        for symbol,date in [(raw['old_symbol'],prior),(raw['new_symbol'],day)]:
            listings[symbol,date]=reader.record(symbol,date)
        reviews.append(review)
    merge(reader.inputs)
    events,pending=compile_renames(pending,reviews,listings,
        pd.read_parquet(args.history/'history.parquet'),cal)
    report=dict(reviewed_name_change_records=len(events),securities=len({r['security_id'] for r in events}),
        unresolved_original_records=len(pending),chart_factors_added=0,
        option_deliverables_admitted=False,research_ready=False)
    if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Rename review input changed')
    with transaction(args.output) as temp:
        for name,value in [('inputs',inputs),('report',report),('events',events),('unresolved',pending),('reviews',doc)]:
            (temp/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
        receipt(temp,dict(identity=identity(inputs),research_ready=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
