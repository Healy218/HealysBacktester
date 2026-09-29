#!/usr/bin/env python3
"""Compare a stopped pending replay against independent per-horizon execution."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import zlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nn_meta.v7.storage import verify,sha,identity,receipt,transaction
from incubator.continual.storage import write


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.full_execution import ExecutionWorker
    from nn_meta.v7.execution_cohorts import members_for_bucket
    from nn_meta.v7.execution_jobs import proposal_from_key
    from nn_meta.v7.entry_demand import selection_id
    from nn_meta.v7.epoch_references import EpochContractReferences
    from nn_meta.v7.reviewed_references import ReviewedContractReferences
    from nn_meta.v7.contract_blackouts import BlackoutPolicy,BlackoutReferences
    from nn_meta.v7.dated_hours import DatedHours
    from nn_meta.v7.packed_quote_index import IndexedQuoteArchive
    p=argparse.ArgumentParser()
    for n in ['wave','jobs','references','review','hours','blackouts','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--limit',type=int,default=1000);a=p.parse_args()
    for n,v in vars(a).items():
        if isinstance(v,Path):setattr(a,n,v.resolve())
    meter=json.loads((a.wave/'progress.json').read_text())
    if meter['status'] not in ['checkpointed','replayed_pending']:raise ValueError('Stopped pilot required')
    sid=meter['security_id'];root=a.wave/'securities'/sid;verify(a.jobs)
    inputs={str(p):sha(p) for p in [root/'wave.sqlite3',a.wave/'declaration.json',a.jobs/'complete.json',Path(__file__).resolve()]}
    binding=json.loads((a.jobs/'binding.json').read_text());base=EpochContractReferences(a.references,security_id=sid)
    reviewed=ReviewedContractReferences(base,a.review);archive=IndexedQuoteArchive(a.wave/'indexes'/sid)
    worker=ExecutionWorker(binding['demand'],archive,BlackoutReferences(reviewed,BlackoutPolicy(a.blackouts)),DatedHours(a.hours))
    checked=0
    try:
        with sqlite3.connect((root/'wave.sqlite3').as_uri()+'?mode=ro',uri=True) as wave,sqlite3.connect((a.jobs/'jobs.sqlite3').as_uri()+'?mode=ro',uri=True) as jobs:
            groups={}
            for encoded,payload in wave.execute('SELECT coverage,result FROM buckets JOIN contents USING(content_id)'):
                b=json.loads(encoded);b['result']=json.loads(zlib.decompress(payload));k=b['source_key'];groups.setdefault((k[0],k[1],k[4],b['target_dte']),[]).append(b)
            if sum(b['members'] for bs in groups.values() for b in bs)>a.limit:raise ValueError('Pilot comparison exceeds explicit limit')
            for (symbol,clock,side,target),bs in groups.items():
                rows=list(jobs.execute('SELECT * FROM jobs WHERE symbol=? AND decision_ns=? AND is_put=? ORDER BY symbol,decision_ns,exit_ns,censored_ns,is_put,exit_symbol',(symbol,clock,side)))
                seen=set()
                for b in sorted(bs,key=lambda x:x['ordinal']):
                    members=members_for_bucket(b,rows,sid,seen)
                    for row in members:
                        proposal=proposal_from_key(row[:6],sid);actual=worker.run(proposal,target)
                        expected=json.loads(json.dumps(b['result']));expected.pop('shared_result_id',None)
                        # Shared payloads retain their first target identity; restore this bucket target.
                        expected['selection_id']=selection_id(symbol,clock,'P' if side else 'C',target)
                        if 'proposal_id' in expected:expected['proposal_id']=proposal['proposal_id']
                        if 'replay' in expected:expected['replay']['proposal_id']=proposal['proposal_id']
                        if actual!=expected:
                            print(json.dumps({k:dict(actual=actual.get(k),expected=expected.get(k)) for k in actual.keys()|expected.keys() if actual.get(k)!=expected.get(k)},sort_keys=True))
                            raise ValueError('Independent replay differs: '+proposal['proposal_id'])
                        checked+=1
                    seen.update(tuple(r[:6]) for r in members)
                if len(seen)!=len(rows):raise ValueError('Omitted cohort members')
        if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Pilot changed during audit')
        if not checked:raise ValueError('No independent paths compared')
        report=dict(independent_horizon_targets=checked,exact_parity=True,full_execution_coverage=False)
        with transaction(a.output) as t:
            write(t/'binding.json',dict(inputs=inputs));write(t/'report.json',report);receipt(t,dict(identity=identity(inputs)))
        print(json.dumps(report))
    finally:worker.close();archive.close();base.close()


if __name__=='__main__':main()
