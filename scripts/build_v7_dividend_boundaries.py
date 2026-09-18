"""Seal named cash-only boundary facts; preserve the frozen trading membership."""
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
    from nn_meta.v7.dividend_boundaries import add_boundary_view,observed_day
    from nn_meta.v7.dividend_producer_versions import historical_input_bindings
    from nn_meta.v7.listed_evidence import ListedEvidence
    from nn_meta.v7.coverage import receipt_frame
    from nn_meta.v7.storage import identity,sha,verify,receipt,transaction
    parser=argparse.ArgumentParser(description=__doc__)
    for n in ('history','daily','supplement','listings','warmup-listings','calendar','inventory','requests','output'):
        parser.add_argument('--'+n,type=Path,required=True)
    args=parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta') or shutil.disk_usage(ROOT).free<100*1024**3:
        raise ValueError('Repository artifact disk and reserve required')
    inputs={}
    def merge(values):
        for p,d in historical_input_bindings(values).items():
            if p in inputs and inputs[p]!=d:raise ValueError('Conflicting source binding')
            inputs[p]=d
    def bind(path):
        doc=verify(path);merge({str(path/'complete.json'):sha(path/'complete.json')})
        merge({str(path/n):d for n,d in doc['files'].items()})
        if (path/'inputs.json').exists():merge(json.loads((path/'inputs.json').read_text()))
        return doc
    for p in (args.history,args.calendar.parent,args.inventory):bind(p)
    for p in [Path(__file__),args.requests,ROOT/'nn_meta/session_calendar.py',
              *[ROOT/'nn_meta/v7'/(n+'.py') for n in ('dividend_boundaries','dividend_review_extensions',
              'dividend_producer_versions','listed_evidence','daily_identities','coverage','stock_daily','storage','runtime')]]:
        merge({str(p):sha(p)})
    document=json.loads(args.requests.read_text())
    if document['schema']!='v7-finite-dividend-boundaries-v1':raise ValueError('Finite boundary requests required')
    before=pd.read_parquet(args.history/'history.parquet');result=before.copy()
    calendar=SessionCalendar(json.loads(args.calendar.read_text()))
    readers=[ListedEvidence(args.listings),ListedEvidence(args.warmup_listings)]
    originals=json.loads((args.inventory/'candidates.json').read_text())
    request_keys=set()
    for request in document['requests']:
        key=request['source_symbol'],request['ex_date']
        if key in request_keys:raise ValueError('Unique finite dividend boundary requests required')
        request_keys.add(key)
        for e in request.get('primary_identity_evidence',[]):
            p=Path(e['capture']);doc=bind(p)
            if sha(p/'complete.json')!=e['receipt_sha256'] or doc['files']['response.bin']!=e['payload_sha256']:
                raise ValueError('Primary identity evidence changed')
        if request['mode']=='primary_cusip_cash_security':
            original=[r for r in originals if r['provider']=='alpaca' and r['category']=='cash'
                      and r['subject_symbol']==request['source_symbol'] and r['effective_date']==request['ex_date']]
            if not original or any(r['record'].get('cusip')!=request['cusip'] for r in original):
                raise ValueError('Original dividend CUSIP differs from reviewed primary identity')
        facts=[];listings=[]
        for day in (request['prior_date'],request['ex_date']):
            reader=readers[1 if day<before.source_date.min() else 0]
            listing=reader.record(request['source_symbol'],day)
            if not listing:raise ValueError('Missing exact-day listed witness')
            listings.append(listing)
            p=args.supplement/'stock_1m/raw'/request['source_symbol']/day
            if (p/'complete.json').exists():
                bind(p);doc,raw=receipt_frame(args.supplement,p/'complete.json')
                if (doc['task'].get('adjustment')!='raw' or doc['task'].get('symbol')!=request['source_symbol']
                        or doc['task'].get('start')!=day+'T00:00:00Z'):
                    raise ValueError('Exact named raw minute capture required')
                fact=observed_day(raw,calendar,request['source_symbol'],day)
            else:
                p=args.daily/'shards'/request['source_symbol']/day[:4];bind(p)
                declaration=json.loads((p/'declaration.json').read_text());merge(declaration['inputs']);merge(declaration['sources'])
                frame=pd.read_parquet(p/'daily.parquet');selected=frame[frame.source_date.eq(day)]
                if len(selected)!=1 or selected.stock_ticker.iloc[0]!=request['source_symbol']:
                    raise ValueError('Exact named daily source required')
                fact=selected.iloc[0].to_dict()
            facts.append(fact)
        result=add_boundary_view(result,facts,request,listings,calendar,
            scoped_ids=set(before.security_id),study_start=before.source_date.min())
    for reader in readers:merge(reader.inputs)
    eligible=pd.read_parquet(args.history/'eligible_sources.parquet')
    # No boundary is added to or substituted into the trading membership artifact.
    if any(sha(p)!=d for p,d in inputs.items()):raise ValueError('Boundary source bytes changed')
    report=dict(original_history_rows=len(before),dividend_view_rows=len(result),
        named_boundaries=len(document['requests']),cash_only_additional_security_ids=sorted(set(result.security_id)-set(before.security_id)),
        eligible_sessions=len(eligible),changes_trading_eligibility=False,bridges_reorganization=False,
        use='dividend price/cash compilation only; not a new eligible security history',research_ready=False)
    with transaction(args.output) as temp:
        result.to_parquet(temp/'history.parquet',index=False)
        shutil.copyfile(args.history/'eligible_sources.parquet',temp/'eligible_sources.parquet')
        for n,v in [('inputs',inputs),('report',report),('requests',document)]:
            (temp/(n+'.json')).write_text(json.dumps(v,indent=2)+'\n')
        receipt(temp,dict(identity=identity(inputs),research_ready=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
