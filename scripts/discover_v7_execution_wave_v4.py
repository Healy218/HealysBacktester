#!/usr/bin/env python3
"""Discover full-universe actual input frontiers using proven horizon cohorts."""
import argparse
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
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['plan','base-index','entry-root','references','review','hours','blackouts','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--max-seconds',type=int,default=28800)
    parser.add_argument('--max-cohorts',type=int,default=0)
    parser.add_argument('--security')
    parser.add_argument('--checkpoint-from',type=Path)
    parser.add_argument('--commit-cohorts',type=int,default=8)
    args=parser.parse_args()
    from nn_meta.v7.reviewed_blackouts import exclusion_phase
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.storage import sha,verify,identity
    from nn_meta.v7.execution_jobs import guard
    from nn_meta.v7.execution_cohorts import cohorts,cover_horizons
    from nn_meta.v7.full_execution import ExecutionWorker,build_security_quote_index
    from nn_meta.v7.execution_prefix_cache_v2 import SharedExecutionWorker
    from nn_meta.v7.indexed_references import IndexedContractReferences
    from nn_meta.v7.reviewed_references import ReviewedContractReferences
    from nn_meta.v7.contract_blackouts import BlackoutReferences,BlackoutPolicy
    from nn_meta.v7.dated_hours import DatedHours
    from nn_meta.v7.packed_quote_index_v2 import IndexedQuoteArchive
    from nn_meta.v7.wave_performance_v1 import Writer, selected_pending
    from nn_meta.v7.checkpoint_clone_v1 import inherit_checkpoint
    from incubator.continual.storage import write
    for name,value in vars(args).items():
        if isinstance(value,Path):setattr(args,name,value.resolve())
    if args.max_seconds<1 or args.max_cohorts<0 or not args.output.is_relative_to(ROOT/'nn_meta/validation'):
        parser.error('Bounded budgets and separate validation root required')
    plan=json.loads((args.plan/'declaration.json').read_text())
    if args.security and args.security not in plan['securities']:parser.error('Foreign security')
    securities=[args.security] if args.security else plan['securities']
    modules=['checkpoint_clone_v1.py','wave_performance_v1.py','packed_quote_index_v2.py','packed_quotes_v3.py','reviewed_blackouts.py','execution_cohorts.py','execution_prefix_cache_v2.py','execution_jobs.py','full_execution.py',
             'replay_clocks.py','replay_stream.py','execution_frontier_v2.py','indexed_references.py',
             'reviewed_references.py','packed_quote_index.py','packed_quotes.py','packed_quotes_v2.py',
             'chain.py','execution.py','quote_archive.py','contract_blackouts.py','dated_hours.py']
    inputs={str(ROOT/'nn_meta/v7'/name):sha(ROOT/'nn_meta/v7'/name) for name in modules}
    for path in [Path(__file__),args.plan/'declaration.json',ROOT/'options/paper_risk.py',ROOT/'options/paper_pricing.py']:
        inputs[str(path.resolve())]=sha(path)
    for root in [args.base_index,args.references,args.review,args.hours,args.blackouts]:
        verify(root);inputs[str(root/'complete.json')]=sha(root/'complete.json')
    declaration=dict(schema='v7-full-execution-cohort-wave-v2',inputs=inputs,securities=securities,
                     plan=str(args.plan),entry_root=str(args.entry_root),full_universe_scope=not bool(args.security))
    declaration['performance_revision']='wave-performance-v1'
    declaration['commit_cohorts']=args.commit_cohorts
    if args.checkpoint_from:
        if not args.security:parser.error('Checkpoint inheritance requires one security')
        declaration['checkpoint_parent']=str(args.checkpoint_from)
    args.output.mkdir(parents=True,exist_ok=True)
    lock=(args.output/'lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    anchor=args.output/'declaration.json'
    if anchor.exists() and json.loads(anchor.read_text())!=declaration:raise ValueError('Wave inputs changed; use a new epoch')
    if args.checkpoint_from:
        inherit_checkpoint(args.checkpoint_from,args.output,declaration,args.security)
    write(anchor,declaration)
    hours=DatedHours(args.hours);policy=BlackoutPolicy(args.blackouts)
    began=time.monotonic();deadline=began+args.max_seconds;new_cohorts=0;finished=0;last_report=began
    try:
        for sid in securities:
            jobs=args.plan/'jobs'/sid
            if not (jobs/'complete.json').exists():
                write(args.output/'progress.json',dict(status='awaiting_job_plan',security_id=sid,
                      securities_discovered=finished,securities_required=len(securities),full_execution_coverage=False))
                break
            verify(jobs);job_binding=json.loads((jobs/'binding.json').read_text())
            expected=json.loads((jobs/'report.json').read_text())
            index=build_security_quote_index(job_binding['demand'],args.base_index,args.entry_root,args.output/'indexes'/sid)
            root=args.output/'securities'/sid;root.mkdir(parents=True,exist_ok=True)
            binding=dict(campaign_identity=identity(declaration),jobs_sha256=sha(jobs/'complete.json'),quote_index_sha256=sha(index/'complete.json'))
            if (root/'binding.json').exists() and json.loads((root/'binding.json').read_text())!=binding:
                raise ValueError('Wave checkpoint inputs changed')
            write(root/'binding.json',binding)
            db=sqlite3.connect(root/'wave.sqlite3')
            db.executescript('''PRAGMA cache_size=-8192; PRAGMA synchronous=FULL; PRAGMA temp_store=FILE;
                CREATE TABLE IF NOT EXISTS cohorts(symbol,decision_ns,is_put,horizons,proposals,
                    PRIMARY KEY(symbol,decision_ns,is_put)) WITHOUT ROWID;
                CREATE TABLE IF NOT EXISTS contents(content_id PRIMARY KEY,result BLOB) WITHOUT ROWID;
                CREATE TABLE IF NOT EXISTS buckets(bucket_id PRIMARY KEY,target,coverage TEXT,content_id,
                    status,members,proposal_weight,label_complete) WITHOUT ROWID;
                CREATE TABLE IF NOT EXISTS exclusions(bucket_id PRIMARY KEY,phase,members,proposal_weight) WITHOUT ROWID;
                CREATE TABLE IF NOT EXISTS pending(request_id PRIMARY KEY,request TEXT) WITHOUT ROWID;
                CREATE TABLE IF NOT EXISTS links(bucket_id,request_id,PRIMARY KEY(bucket_id,request_id)) WITHOUT ROWID;''')
            base=IndexedContractReferences(args.references,security_id=sid)
            reviewed=ReviewedContractReferences(base,args.review)
            archive=IndexedQuoteArchive(index,cache_packs=4)
            worker=SharedExecutionWorker(ExecutionWorker(job_binding['demand'],archive,BlackoutReferences(reviewed,policy),hours))
            writer=Writer(db,args.commit_cohorts)
            exhausted=True
            def report(status):
                writer.flush()
                counts=writer.summary('perf_status','members')
                weights=writer.summary('perf_status','weight')
                value=dict(status=status,security_id=sid,securities_discovered=finished,securities_required=len(securities),
                    cohorts_discovered=writer.counts('cohorts'),
                    distinct_horizon_targets_covered=sum(counts.values()),horizon_target_statuses=counts,
                    proposal_target_rows_covered=sum(weights.values()),proposal_target_statuses=weights,
                    execution_buckets=writer.counts('buckets'),
                    retained_payloads=writer.counts('contents'),
                    pending_requests=writer.counts('pending'),
                    exclusion_horizon_targets=writer.summary('perf_exclusions','members'),
                    exclusion_proposal_targets=writer.summary('perf_exclusions','weight'),
                    elapsed_seconds=time.monotonic()-began,updated_at=datetime.now(timezone.utc).isoformat(),
                    full_execution_coverage=False,research_ready=False)
                write(root/'progress.json',value);write(args.output/'progress.json',value)
                print(json.dumps(value),flush=True)
            try:
                with sqlite3.connect((jobs/'jobs.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True) as source:
                    source.execute('PRAGMA cache_size=-4096')
                    for key,rows in writer.cohorts(source):
                        if db.execute('SELECT 1 FROM cohorts WHERE symbol=? AND decision_ns=? AND is_put=?',key).fetchone():continue
                        if time.monotonic()>=deadline or (args.max_cohorts and new_cohorts>=args.max_cohorts):
                            exhausted=False;break
                        with writer.cohort(key):
                            for target in job_binding['targets']:
                                members=weight=0
                                for bucket in cover_horizons(rows,sid,target,worker.run):
                                    result=bucket.pop('result')
                                    bucket_id=identity(dict(cohort=key,target=target,ordinal=bucket['ordinal']))
                                    content_id=result.get('shared_result_id',bucket_id)
                                    if not db.execute('SELECT 1 FROM contents WHERE content_id=?',(content_id,)).fetchone():
                                        db.execute('INSERT INTO contents VALUES(?,?)',(content_id,zlib.compress(json.dumps(result,sort_keys=True,allow_nan=False).encode())))
                                    db.execute('INSERT INTO buckets VALUES(?,?,?,?,?,?,?,?)',(bucket_id,target,json.dumps(bucket,sort_keys=True),content_id,
                                        result['status'],bucket['members'],bucket['proposal_weight'],int(result['label_complete'])))
                                    phase=exclusion_phase(result)
                                    if phase:
                                        db.execute('INSERT INTO exclusions VALUES(?,?,?,?)',(bucket_id,phase,bucket['members'],bucket['proposal_weight']))
                                    for request in result['pending']:
                                        encoded=json.dumps(request,sort_keys=True)
                                        old=db.execute('SELECT request FROM pending WHERE request_id=?',(request['request_id'],)).fetchone()
                                        if old and old[0]!=encoded:raise ValueError('Request identity changed')
                                        db.execute('INSERT OR IGNORE INTO pending VALUES(?,?)',(request['request_id'],encoded))
                                        db.execute('INSERT INTO links VALUES(?,?)',(bucket_id,request['request_id']))
                                    members+=bucket['members'];weight+=bucket['proposal_weight']
                                if members!=len(rows) or weight!=sum(row[6] for row in rows):raise ValueError('Cohort membership census differs')
                            db.execute('INSERT INTO cohorts VALUES(?,?,?,?,?)',(*key,len(rows),sum(row[6] for row in rows)))
                        new_cohorts+=1
                        if time.monotonic()-last_report>=15:
                            report('running');last_report=time.monotonic()
                            guard(args.output,max_bytes=20_000_000_000,reserve_bytes=20_000_000_000)
                writer.flush()
                consumed={**worker.inputs,**reviewed.inputs,**policy.inputs,**hours.inputs}
                if any(sha(path)!=digest for path,digest in consumed.items()):raise ValueError('Consumed wave input changed')
                write(root/'consumed-inputs.json',consumed)
                if exhausted:
                    observed=db.execute('SELECT SUM(horizons),SUM(proposals) FROM cohorts').fetchone()
                    if observed!=(expected['distinct_horizons'],expected['proposals']):raise ValueError('Security horizon census differs')
                    finished+=1
                report('discovered' if exhausted else 'checkpointed')
            finally:
                worker.close();archive.close();base.close();db.close()
            if not exhausted:break
        if any(sha(path)!=digest for path,digest in inputs.items()):raise ValueError('Wave runtime changed')
    except Exception as exc:
        write(args.output/'failure.json',dict(type=type(exc).__name__,error=str(exc),observed_at=datetime.now(timezone.utc).isoformat()))
        raise


if __name__=='__main__':main()
