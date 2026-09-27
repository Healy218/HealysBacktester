#!/usr/bin/env python3
"""Bound first-leg execution quote needs from every frozen selected contract.

These envelopes are conservative potential holds through expiry/history end,
not realized paths or a claim to cover later roll contracts or stock delivery.
They retain exact incremental seconds beyond existing pre-entry quote demand.
"""
import argparse
from collections import Counter
from concurrent.futures import as_completed
import json
from pathlib import Path
import sqlite3
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def work(job):
    sid,source_text,digest,hours_text,blackouts_text,destination_text=job
    from nn_meta.v7.storage import sha,verify,identity,receipt,transaction
    from nn_meta.v7.dated_hours import DatedHours,MINUTE
    from nn_meta.v7.contract_blackouts import BlackoutPolicy
    from options.data.provider import parse_occ_symbol
    import pandas as pd
    from bisect import bisect_left,bisect_right
    source,destination=Path(source_text),Path(destination_text)
    if sha(source/'complete.json')!=digest:raise ValueError('Frozen demand receipt changed')
    head=verify(source)
    hours=DatedHours(hours_text);blackouts=BlackoutPolicy(blackouts_text)
    inputs={str(source/'complete.json'):digest,str(Path(__file__).resolve()):sha(__file__)}
    inputs.update({str(source/n):h for n,h in head['files'].items()})
    inputs.update(hours.inputs);inputs.update(blackouts.inputs)
    binding=dict(inputs=inputs,scope='first-leg conservative envelope, not realized execution demand')
    if destination.exists():
        verify(destination,expected_identity=identity(binding))
        return sid,json.loads((destination/'report.json').read_text())
    decl=json.loads((source/'declaration.json').read_text())
    days=[d for d in hours.days if decl['start']<=d<=decl['end']]
    counts=Counter();years=Counter();crossings=[]
    with transaction(destination) as temp:
        with sqlite3.connect((source/'demand.sqlite3').as_uri()+'?mode=ro',uri=True) as db, sqlite3.connect(temp/'envelopes.sqlite3') as out:
            out.executescript('PRAGMA temp_store=FILE; PRAGMA cache_size=-8192; CREATE TABLE windows(contract TEXT,date TEXT,start_ns INTEGER,end_ns INTEGER,existing_quote_ns INTEGER,additional_quote_ns INTEGER,blackout INTEGER,PRIMARY KEY(contract,date)) WITHOUT ROWID;')
            clauses=[];params=[]
            for contract,day in blackouts.treatments:
                lo=pd.Timestamp(day,tz='America/New_York').value
                hi=(pd.Timestamp(day,tz='America/New_York')+pd.DateOffset(days=1)).value
                clauses.append('(contract=? AND decision_ns>=? AND decision_ns<?)');params.extend([contract,lo,hi])
            where='status="selected" AND NOT ('+' OR '.join(clauses)+')'
            rows=db.execute('SELECT contract,MIN(decision_ns),COUNT(*) FROM selections WHERE '+where+' GROUP BY contract ORDER BY contract',params)
            # Ordered existing windows are streamed once, not rescanned for every contract.
            existing=iter(db.execute('SELECT contract,date,start_ns,end_ns FROM requests WHERE kind="quotes" ORDER BY contract,date,start_ns,end_ns'))
            current=next(existing,None)
            for contract,first,selections in rows:
                root,expiry,_,_=parse_occ_symbol(contract)
                firstday=pd.Timestamp(first,unit='ns',tz='UTC').tz_convert('America/New_York').date().isoformat()
                firstday_index=bisect_left(days,firstday)
                final=min(expiry.isoformat(),decl['end'])
                while current is not None and current[0]<contract:current=next(existing,None)
                counts['contracts']+=1;counts['selection_outcomes']+=selections
                for day in days[firstday_index:bisect_right(days,final)]:
                    session=hours.at(root,day)
                    lo=max(session['open_ns'],first-30_000_000_000) if day==firstday else session['open_ns']
                    hi=session['close_ns']
                    while current is not None and current[:2]<(contract,day):current=next(existing,None)
                    covered=0;last=lo
                    while current is not None and current[:2]==(contract,day):
                        a,b=max(lo,current[2]),min(hi,current[3])
                        if b>max(a,last):covered+=b-max(a,last);last=b
                        current=next(existing,None)
                    if hi<=lo:continue
                    blackout=int(blackouts.at(contract,day) is not None)
                    out.execute('INSERT INTO windows VALUES(?,?,?,?,?,?,?)',(contract,day,lo,hi,covered,hi-lo-covered,blackout))
                    counts['contract_days']+=1;counts['envelope_quote_ns']+=hi-lo
                    counts['existing_quote_ns']+=covered;counts['additional_quote_ns']+=hi-lo-covered
                    years[day[:4]]+=hi-lo-covered
                    if blackout:
                        # Retain as a possible crossing, never claim actual held exposure.
                        crossings.append(dict(contract=contract,date=day,first_selected_date=firstday))
                if counts['contracts']%2048==0:
                    import shutil
                    if shutil.disk_usage(temp).free<20*1024**3:
                        raise ValueError('Execution planning must preserve the 20 GiB reserve')
                    out.commit()
        report=dict(security_id=sid,**counts,additional_quote_ns_by_year=dict(years),potential_blackout_crossings=crossings,
                    realized_paths=False,roll_contracts_included=False,physical_stock_included=False,
                    research_ready=False,full_execution_coverage=False)
        if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Execution-envelope input drift')
        for name,doc in [('binding.json',binding),('report.json',report)]:
            (temp/name).write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
        receipt(temp,dict(identity=identity(binding),research_ready=False))
    return sid,report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit',type=Path,required=True);p.add_argument('--hours',type=Path,required=True)
    p.add_argument('--blackouts',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--workers',type=int,required=True)
    args=p.parse_args()
    from nn_meta.v7.runtime import configure_threads,worker_pool
    configure_threads(1)
    from nn_meta.v7.storage import sha,verify,identity,transaction,receipt
    for k in ('audit','hours','blackouts','output'):setattr(args,k,getattr(args,k).resolve())
    if not args.output.is_relative_to(ROOT/'nn_meta/validation'):p.error('Use separate validation output')
    verify(args.audit);parent=json.loads((args.audit/'report.json').read_text());audit=json.loads((args.audit/'binding.json').read_text())
    source=Path(audit['demand_root'])/'demand';checkpoints=args.output.with_suffix('.checkpoints')
    # Measured demand inputs already exist; bound small planning output to 2 GiB plus reserve.
    import shutil
    if shutil.disk_usage(ROOT).free<22*1024**3:raise ValueError('Planning allowance plus 20 GiB reserve unavailable')
    results={}
    with worker_pool(args.workers,threads=1) as pool:
        jobs=[(sid,str(source/sid),parent['inputs'][str(source/sid/'complete.json')],str(args.hours),str(args.blackouts),str(checkpoints/sid)) for sid in audit['securities']]
        for future in as_completed([pool.submit(work,job) for job in jobs]):
            sid,report=future.result();results[sid]=report
            if len(results)%25==0:print(f'Execution envelopes {len(results)}/{len(jobs)}',flush=True)
    totals={k:sum(r.get(k,0) for r in results.values()) for k in ('contracts','selection_outcomes','contract_days','envelope_quote_ns','existing_quote_ns','additional_quote_ns')}
    report=dict(schema='v7-execution-envelopes-v1',securities=len(results),**totals,
                potential_blackout_crossings=[dict(security_id=sid,**c) for sid,r in sorted(results.items()) for c in r['potential_blackout_crossings']],
                checkpoints={sid:sha(checkpoints/sid/'complete.json') for sid in sorted(results)},
                scope='Conservative first legs to expiry/history end; excludes realized stops, signal exits, new roll contracts and physical stock.',
                full_execution_coverage=False,research_ready=False)
    binding=dict(audit_sha256=sha(args.audit/'complete.json'),hours_sha256=sha(args.hours/'complete.json'),
                 blackout_sha256=sha(args.blackouts/'complete.json'),producer_sha256=sha(__file__))
    if args.output.exists():verify(args.output,expected_identity=identity(binding))
    else:
        with transaction(args.output) as temp:
            for name,doc in [('binding.json',binding),('report.json',report)]:
                (temp/name).write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
            receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps({k:v for k,v in report.items() if k not in ('checkpoints','potential_blackout_crossings')},indent=2))


if __name__=='__main__':main()
