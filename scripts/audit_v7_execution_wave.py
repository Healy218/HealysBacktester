#!/usr/bin/env python3
"""Compare cohort reconstruction with retained independent per-horizon replay."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['wave','flat','jobs','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    from nn_meta.v7.storage import sha,identity,verify,receipt,transaction
    from nn_meta.v7.execution_cohorts import members_for_bucket
    from nn_meta.v7.execution_jobs import proposal_from_key
    from nn_meta.v7.execution_results import load_result
    from nn_meta.v7.entry_demand import selection_id
    for name,path in vars(a).items():setattr(a,name,path.resolve())
    verify(a.jobs);sid=json.loads((a.jobs/'binding.json').read_text())['security_id']
    inputs={str(Path(__file__).resolve()):sha(__file__),str(a.jobs/'complete.json'):sha(a.jobs/'complete.json')}
    for root,db_name in [(a.wave,'wave.sqlite3'),(a.flat,'paths.sqlite3')]:
        if json.loads((root/'progress.json').read_text())['status'] not in ('checkpointed','discovered'):
            raise ValueError('Audit a stopped checkpoint')
        for name in ['binding.json','consumed-inputs.json',db_name]:inputs[str(root/name)]=sha(root/name)
    checked=covered=buckets=0
    with sqlite3.connect((a.wave/'wave.sqlite3').as_uri()+'?mode=ro',uri=True) as wave, \
         sqlite3.connect((a.flat/'paths.sqlite3').as_uri()+'?mode=ro',uri=True) as flat, \
         sqlite3.connect((a.jobs/'jobs.sqlite3').as_uri()+'?mode=ro',uri=True) as jobs:
        groups={}
        for coverage,payload in wave.execute('SELECT b.coverage,c.result FROM buckets b JOIN contents c USING(content_id)'):
            bucket=json.loads(coverage);bucket['result']=json.loads(zlib.decompress(payload))
            k=bucket['source_key'];group=(k[0],k[1],k[4],bucket['target_dte'])
            groups.setdefault(group,[]).append(bucket)
        for (symbol,clock,side,target),entries in groups.items():
            rows=list(jobs.execute('SELECT * FROM jobs WHERE symbol=? AND decision_ns=? AND is_put=? ORDER BY symbol,decision_ns,exit_ns,censored_ns,is_put,exit_symbol',(symbol,clock,side)))
            seen=set()
            for bucket in sorted(entries,key=lambda b:b['ordinal']):
                members=members_for_bucket(bucket,rows,sid,seen)
                covered+=len(members);buckets+=1
                for row in members:
                    proposal=proposal_from_key(row[:6],sid)
                    path_id=identity(dict(proposal_id=proposal['proposal_id'],target_dte=target))
                    try:expected=load_result(flat,path_id)
                    except KeyError:continue
                    actual=json.loads(json.dumps(bucket['result']))
                    actual.pop('shared_result_id',None)
                    if 'proposal_id' in actual:actual['proposal_id']=proposal['proposal_id']
                    if 'replay' in actual:actual['replay']['proposal_id']=proposal['proposal_id']
                    actual.update(path_id=path_id,target_dte=target,security_id=sid,source_horizon=proposal,
                        source_multiplicity=row[6],selection_id=selection_id(symbol,clock,'P' if side else 'C',target))
                    if actual!=expected:raise ValueError('Cohort differs from independent retained replay: '+path_id)
                    checked+=1
                seen.update(tuple(row[:6]) for row in members)
            if len(seen)!=len(rows):raise ValueError('Cohort audit missed an original horizon')
    if not checked:raise ValueError('No overlapping independent execution evidence')
    if any(sha(path)!=digest for path,digest in inputs.items()):raise ValueError('Audit checkpoint changed')
    report=dict(independent_paths_compared=checked,horizon_targets_reconstructed=covered,buckets=buckets,
                exact_parity=True,full_execution_coverage=False,research_ready=False)
    with transaction(a.output) as temp:
        for name,doc in [('binding.json',dict(inputs=inputs)),('report.json',report)]:
            (temp/name).write_text(json.dumps(doc,sort_keys=True,indent=2)+'\n')
        receipt(temp,dict(identity=identity(inputs),research_ready=False))
    print(json.dumps(report))


if __name__=='__main__':main()
