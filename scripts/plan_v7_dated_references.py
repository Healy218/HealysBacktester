#!/usr/bin/env python3
"""Derive exact contract/date and root/date reference demand from sealed requests.

No metadata assumptions, broad reference downloads, or execution-path coverage.
"""
from concurrent.futures import as_completed
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def scan(args):
    sid,source_text,digest,destination_text=args
    from nn_meta.v7.storage import verify,sha,identity,transaction,receipt
    from scripts.download_v7_data import save
    from options.data.provider import parse_occ_symbol
    source,destination=Path(source_text),Path(destination_text)
    binding=dict(source_receipt=str(source/'complete.json'),source_sha256=digest,producer_sha256=sha(__file__))
    if sha(source/'complete.json')!=digest:raise ValueError('Demand receipt drift')
    verify(source)
    if destination.exists():
        verify(destination,expected_identity=identity(binding))
        return sid,json.loads((destination/'report.json').read_text())
    dates=Counter();hours=set();count=0
    with transaction(destination) as temp:
        with sqlite3.connect((source/'demand.sqlite3').as_uri()+'?mode=ro',uri=True) as db, sqlite3.connect(temp/'references.sqlite3') as out:
            out.execute('CREATE TABLE requests(contract TEXT,date TEXT,PRIMARY KEY(contract,date)) WITHOUT ROWID')
            for contract,day in db.execute('SELECT contract,date FROM requests GROUP BY contract,date ORDER BY contract,date'):
                root,expiry,right,strike=parse_occ_symbol(contract)
                out.execute('INSERT INTO requests VALUES(?,?)',(contract,day))
                hours.add((root,day));dates[day[:4]]+=1;count+=1
            out.execute('CREATE TABLE hours(symbol TEXT,date TEXT,PRIMARY KEY(symbol,date)) WITHOUT ROWID')
            out.executemany('INSERT INTO hours VALUES(?,?)',sorted(hours))
        report=dict(security_id=sid,contract_dates=count,root_dates=len(hours),years=dict(dates),
            roots=sorted({r for r,d in hours}),scope='Actual pre-entry feature consumers only',
            provider_downloads=0,full_execution_coverage=False,research_ready=False)
        save(temp/'binding.json',binding);save(temp/'report.json',report)
        receipt(temp,dict(identity=identity(binding),research_ready=False))
    return sid,report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--workers',type=int,required=True)
    args=p.parse_args()
    from nn_meta.v7.runtime import configure_threads,worker_pool
    configure_threads(1)
    from nn_meta.v7.storage import verify,sha,identity,transaction,receipt
    from scripts.download_v7_data import save
    args.audit,args.output=args.audit.resolve(),args.output.resolve()
    if not args.output.is_relative_to(ROOT/'nn_meta/validation'):p.error('Use separate validation output')
    verify(args.audit)
    parent=json.loads((args.audit/'report.json').read_text())
    audit=json.loads((args.audit/'binding.json').read_text())
    binding=dict(audit_sha256=sha(args.audit/'complete.json'),producer_sha256=sha(__file__))
    if args.output.exists():verify(args.output,expected_identity=identity(binding));return
    demand=Path(audit['demand_root'])/'demand'
    checkpoint=args.output.with_suffix('.checkpoints')
    results={}
    with worker_pool(args.workers,threads=1) as pool:
        futures=[pool.submit(scan,(sid,str(demand/sid),parent['inputs'][str(demand/sid/'complete.json')],str(checkpoint/sid))) for sid in audit['securities']]
        for future in as_completed(futures):
            sid,report=future.result();results[sid]=report
            if len(results)%50==0:print(f'Dated reference demand {len(results)}/{len(futures)}',flush=True)
    total=sum(r['contract_dates'] for r in results.values())
    if total!=parent['contract_days']:raise ValueError('Dated reference demand differs from exact union')
    report=dict(securities=len(results),contract_dates=total,root_dates=sum(r['root_dates'] for r in results.values()),
        roots=sorted({root for r in results.values() for root in r['roots']}),
        checkpoints={sid:sha(checkpoint/sid/'complete.json') for sid in sorted(results)},
        provider_downloads=0,scope='Pre-entry only; held paths may add dated references/hours',
        full_execution_coverage=False,research_ready=False)
    with transaction(args.output) as temp:
        save(temp/'binding.json',binding);save(temp/'report.json',report)
        receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps({k:v for k,v in report.items() if k not in ('checkpoints','roots')}))


if __name__=='__main__':main()
