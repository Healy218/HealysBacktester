#!/usr/bin/env python3
"""Checkpoint every frozen proposal into the full-universe execution work queue."""
import argparse
from datetime import datetime,timezone
import fcntl
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-seconds',type=int,default=28800)
    p.add_argument('--max-securities',type=int,default=0)
    a=p.parse_args()
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.storage import verify,sha,identity
    from nn_meta.v7.execution_jobs import build_jobs
    from incubator.continual.storage import write
    if a.max_seconds<1 or a.max_securities<0:
        p.error('Positive time and nonnegative scope bound required')
    a.audit,a.output=a.audit.resolve(),a.output.resolve()
    if not a.output.is_relative_to(ROOT/'nn_meta/validation'):
        p.error('Use a separate validation working root')
    verify(a.audit)
    parent=json.loads((a.audit/'binding.json').read_text())
    census=json.loads((a.audit/'report.json').read_text())
    binding=dict(audit=str(a.audit),audit_sha256=sha(a.audit/'complete.json'),
                 producer_sha256=sha(__file__),kernel_sha256=sha(ROOT/'nn_meta/v7/execution_jobs.py'),
                 securities=parent['securities'])
    a.output.mkdir(parents=True,exist_ok=True)
    lock=(a.output/'lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (a.output/'declaration.json').exists() and json.loads((a.output/'declaration.json').read_text())!=binding:
        raise ValueError('Planner contract changed; select a new root')
    write(a.output/'declaration.json',binding)
    began=time.monotonic();deadline=began+a.max_seconds;completed=0;proposals=0;groups=0
    try:
        for sid in parent['securities']:
            source=Path(parent['demand_root'])/'demand'/sid
            report=build_jobs(source,census['inputs'][str(source/'complete.json')],
                a.output/'working'/sid,a.output/'jobs'/sid,deadline=deadline,budget_root=a.output)
            if report['status']=='planned':
                completed+=1;proposals+=report['proposals'];groups+=report['distinct_horizons']
            status=dict(status='running',campaign_identity=identity(binding),updated_at=datetime.now(timezone.utc).isoformat(),
                securities_complete=completed,securities_required=len(parent['securities']),
                proposals_reconciled=proposals,distinct_horizons=groups,last=report,
                elapsed_seconds=time.monotonic()-began,execution_complete=False,research_ready=False)
            write(a.output/'progress.json',status);print(json.dumps(status),flush=True)
            if report['status']!='planned' or (a.max_securities and completed>=a.max_securities):break
        status['status']='planned' if completed==len(parent['securities']) else 'checkpointed'
        write(a.output/'progress.json',status)
    except Exception as exc:
        write(a.output/'failure.json',dict(type=type(exc).__name__,error=str(exc),observed_at=datetime.now(timezone.utc).isoformat()))
        raise


if __name__=='__main__':main()
