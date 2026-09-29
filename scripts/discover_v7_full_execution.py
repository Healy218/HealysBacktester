#!/usr/bin/env python3
"""Resume bounded execution discovery over the complete frozen work queue.

Every path/target is retained on disk. No sample-case selection, contract rerank,
synthetic fill, automatic exclusion or implicit network request is performed.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import fcntl
import json
from pathlib import Path
import sqlite3
import sys
import time
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['plan','base-index','entry-root','references','review','hours','blackouts','output']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--max-seconds',type=int,default=28800)
    p.add_argument('--max-paths',type=int,default=0)
    p.add_argument('--security')
    a=p.parse_args()
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.storage import sha,verify,identity,receipt,transaction
    from nn_meta.v7.execution_jobs import proposal_from_key,guard
    from nn_meta.v7.full_execution import ExecutionWorker,build_security_quote_index
    from nn_meta.v7.indexed_references import IndexedContractReferences
    from nn_meta.v7.reviewed_references import ReviewedContractReferences
    from nn_meta.v7.contract_blackouts import BlackoutReferences,BlackoutPolicy
    from nn_meta.v7.dated_hours import DatedHours
    from nn_meta.v7.packed_quote_index import IndexedQuoteArchive
    from incubator.continual.storage import write
    if a.max_seconds<1 or a.max_paths<0:p.error('Positive time/nonnegative path budgets required')
    for name,value in vars(a).items():
        if isinstance(value,Path):setattr(a,name,value.resolve())
    if not a.output.is_relative_to(ROOT/'nn_meta/validation'):p.error('Use a new validation working root')
    source=json.loads((a.plan/'declaration.json').read_text())
    securities=source['securities']
    if a.security:
        if a.security not in securities:p.error('Security outside frozen universe')
        securities=[a.security]
    modules=['full_execution.py','execution_jobs.py','replay_clocks.py','replay_stream.py',
             'execution_frontier_v2.py','indexed_references.py','reviewed_references.py',
             'packed_quote_index.py','packed_quotes.py','packed_quotes_v2.py','chain.py',
             'execution.py','quote_archive.py','contract_blackouts.py','dated_hours.py']
    inputs={str(ROOT/'nn_meta/v7'/n):sha(ROOT/'nn_meta/v7'/n) for n in modules}
    for path in [Path(__file__),ROOT/'options/paper_risk.py',ROOT/'options/paper_pricing.py',a.plan/'declaration.json']:
        inputs[str(path.resolve())]=sha(path)
    for root in [a.base_index,a.references,a.review,a.hours,a.blackouts]:
        verify(root);inputs[str(root/'complete.json')]=sha(root/'complete.json')
    binding=dict(schema='v7-full-execution-discovery-v1',inputs=inputs,securities=securities,
                 entry_root=str(a.entry_root),plan=str(a.plan),full_universe_scope=not bool(a.security))
    a.output.mkdir(parents=True,exist_ok=True)
    lock=(a.output/'lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (a.output/'declaration.json').exists() and json.loads((a.output/'declaration.json').read_text())!=binding:
        raise ValueError('Discovery inputs changed; use a new epoch root')
    write(a.output/'declaration.json',binding)
    began=time.monotonic();deadline=began+a.max_seconds;new_paths=0;finished=0
    hours=DatedHours(a.hours);blackouts=BlackoutPolicy(a.blackouts)
    summary={}
    try:
        for sid in securities:
            jobs=a.plan/'jobs'/sid
            if not (jobs/'complete.json').exists():
                summary=dict(status='awaiting_job_plan',security_id=sid)
                break
            verify(jobs)
            job_binding=json.loads((jobs/'binding.json').read_text())
            location=a.output/'securities'/sid;location.mkdir(parents=True,exist_ok=True)
            index=build_security_quote_index(job_binding['demand'],a.base_index,a.entry_root,a.output/'indexes'/sid)
            selected=dict(jobs_sha256=sha(jobs/'complete.json'),quote_index_sha256=sha(index/'complete.json'),
                          campaign_identity=identity(binding))
            bound=location/'binding.json'
            if bound.exists() and json.loads(bound.read_text())!=selected:
                raise ValueError('Security checkpoint inputs changed')
            write(bound,selected)
            out=sqlite3.connect(location/'paths.sqlite3')
            out.executescript('''PRAGMA cache_size=-8192; PRAGMA synchronous=FULL; PRAGMA temp_store=FILE;
                CREATE TABLE IF NOT EXISTS paths(path_id TEXT PRIMARY KEY,target INTEGER,multiplicity INTEGER,
                  status TEXT,label_complete INTEGER,result BLOB) WITHOUT ROWID;
                CREATE TABLE IF NOT EXISTS pending(request_id TEXT PRIMARY KEY,request TEXT) WITHOUT ROWID;
                CREATE TABLE IF NOT EXISTS links(path_id TEXT,request_id TEXT,PRIMARY KEY(path_id,request_id)) WITHOUT ROWID;''')
            base=IndexedContractReferences(a.references,security_id=sid)
            reviewed=ReviewedContractReferences(base,a.review)
            references=BlackoutReferences(reviewed,blackouts)
            archive=IndexedQuoteArchive(index,cache_packs=2)
            worker=ExecutionWorker(job_binding['demand'],archive,references,hours)
            exhausted=True
            def report(status):
                nonlocal summary
                counts=dict(out.execute('SELECT status,COUNT(*) FROM paths GROUP BY status'))
                summary=dict(status=status,security_id=sid,paths_evaluated=sum(counts.values()),statuses=counts,
                             proposal_target_rows=out.execute('SELECT COALESCE(SUM(multiplicity),0) FROM paths').fetchone()[0],
                             pending_requests=out.execute('SELECT COUNT(*) FROM pending').fetchone()[0],
                             elapsed_seconds=time.monotonic()-began,updated_at=datetime.now(timezone.utc).isoformat(),
                             full_execution_coverage=False,research_ready=False)
                write(location/'progress.json',summary);write(a.output/'progress.json',summary|{'securities_completed_discovery':finished,'securities_required':len(securities)})
            try:
                with sqlite3.connect((jobs/'jobs.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as db:
                    for row in db.execute('SELECT * FROM jobs ORDER BY symbol,decision_ns,exit_ns,censored_ns,is_put,exit_symbol'):
                        proposal=proposal_from_key(row[:6],sid)
                        for target in job_binding['targets']:
                            path_id=identity(dict(proposal_id=proposal['proposal_id'],target_dte=target))
                            if out.execute('SELECT 1 FROM paths WHERE path_id=?',(path_id,)).fetchone():continue
                            if time.monotonic()>=deadline or (a.max_paths and new_paths>=a.max_paths):
                                exhausted=False;break
                            result=worker.run(proposal,target)
                            result.update(path_id=path_id,target_dte=target,security_id=sid,source_horizon=proposal,
                                          source_multiplicity=row[6])
                            with out:
                                out.execute('INSERT INTO paths VALUES(?,?,?,?,?,?)',(path_id,target,row[6],result['status'],
                                    int(result['label_complete']),zlib.compress(json.dumps(result,sort_keys=True,allow_nan=False).encode())))
                                for request in result['pending']:
                                    encoded=json.dumps(request,sort_keys=True)
                                    old=out.execute('SELECT request FROM pending WHERE request_id=?',(request['request_id'],)).fetchone()
                                    if old and old[0]!=encoded:raise ValueError('Pending request identity collision')
                                    out.execute('INSERT OR IGNORE INTO pending VALUES(?,?)',(request['request_id'],encoded))
                                    out.execute('INSERT INTO links VALUES(?,?)',(path_id,request['request_id']))
                            new_paths+=1
                            if new_paths%25==0:
                                guard(a.output,max_bytes=20_000_000_000,reserve_bytes=20_000_000_000)
                                report('running');print(json.dumps(summary),flush=True)
                        if not exhausted:break
                consumed={**worker.inputs,**reviewed.inputs,**blackouts.inputs,**hours.inputs}
                if any(sha(path)!=digest for path,digest in consumed.items()):raise ValueError('Consumed execution input changed')
                write(location/'consumed-inputs.json',consumed)
                if exhausted:
                    expected=json.loads((jobs/'report.json').read_text())
                    actual=out.execute('SELECT COUNT(*),SUM(multiplicity) FROM paths').fetchone()
                    if actual!=(expected['distinct_horizons']*len(job_binding['targets']),expected['proposal_target_rows']):
                        raise ValueError('Full execution horizon census differs')
                    finished+=1
                report('discovered' if exhausted else 'checkpointed')
            finally:
                worker.close();archive.close();base.close();out.close()
            if not exhausted:break
        if any(sha(path)!=digest for path,digest in inputs.items()):raise ValueError('Discovery source changed')
        write(a.output/'progress.json',summary|dict(securities_completed_discovery=finished,securities_required=len(securities)))
        print(json.dumps(summary),flush=True)
    except Exception as exc:
        write(a.output/'failure.json',dict(type=type(exc).__name__,error=str(exc),observed_at=datetime.now(timezone.utc).isoformat()))
        raise


if __name__=='__main__':main()
