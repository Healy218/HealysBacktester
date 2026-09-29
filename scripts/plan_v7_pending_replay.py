#!/usr/bin/env python3
"""Freeze only source cohorts/targets with real pending requests; preserve old ledgers."""
import argparse
import fcntl
import json
from pathlib import Path
import shutil
import sqlite3
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nn_meta.v7.storage import sha,verify,identity,receipt,transaction
from incubator.continual.storage import write


def pending_targets(db):
    selected={}
    for target,encoded in db.execute('SELECT DISTINCT b.target,b.coverage FROM buckets b JOIN links l USING(bucket_id)'):
        bucket=json.loads(encoded);k=bucket['source_key'];key=(k[0],k[1],k[4])
        if target!=bucket['target_dte']:raise ValueError('Bucket target changed')
        selected.setdefault(key,set()).add(target)
    return selected


def selected_cohorts(source, entries):
    seen=set()
    for entry in entries:
        key=tuple(entry['key'])
        if key in seen or not entry['targets'] or len(set(entry['targets']))!=len(entry['targets']):
            raise ValueError('Duplicate cohort or target in replay plan')
        seen.add(key)
        rows=list(source.execute('SELECT * FROM jobs WHERE symbol=? AND decision_ns=? AND is_put=? '
            'ORDER BY symbol,decision_ns,exit_ns,censored_ns,is_put,exit_symbol',key))
        if len(rows)!=entry['horizons'] or sum(r[6] for r in rows)!=entry['proposals']:
            raise ValueError('Replay membership differs from frozen job census')
        yield key,rows


def plan(parent,jobs,output):
    parent,jobs,output=[Path(p).resolve() for p in (parent,jobs,output)]
    guard=(parent/'lock').open('a');fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
    inputs={str(p):sha(p) for p in [parent/'declaration.json',jobs/'declaration.json',Path(__file__).resolve()]}
    observations={};count=0
    with transaction(output) as t:
        for path in sorted((parent/'waves').glob('*/securities/*/wave.sqlite3')):
            sid=path.parent.name;wave=path.parents[2]
            lock=(wave/'lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            # Preserve physical pre-recovery images for hot journals.
            sidecars=[Path(str(path)+s) for s in ['-journal','-wal'] if Path(str(path)+s).exists()]
            before=sha(path);recovery={}
            if sidecars:
                backup=output.with_suffix('.recovery')/sid;backup.mkdir(parents=True,exist_ok=True)
                for p in [path,*sidecars]:
                    
                    if not (backup/p.name).exists():shutil.copy2(p,backup/p.name)
                    if sha(p)!=sha(backup/p.name):raise ValueError('Existing recovery preimage differs')
                    recovery[str(backup/p.name)]=sha(backup/p.name)
            with sqlite3.connect(path.as_uri()+'?mode=rw',uri=True) as db:
                if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise ValueError('Original checkpoint integrity failure')
                selected=pending_targets(db)
            job=jobs/'jobs'/sid;verify(job);inputs[str(job/'complete.json')]=sha(job/'complete.json')
            inputs[str(wave/'declaration.json')]=sha(wave/'declaration.json')
            index=wave/'indexes'/sid;verify(index)
            binding=json.loads((path.parent/'binding.json').read_text());declaration=json.loads((wave/'declaration.json').read_text())
            if binding['campaign_identity']!=identity(declaration) or binding['quote_index_sha256']!=sha(index/'complete.json'):
                raise ValueError('Checkpoint binding differs')
            for p,h in declaration['inputs'].items():
                if sha(p)!=h:raise ValueError('Frozen wave input differs')
            entries=[]
            with sqlite3.connect((job/'jobs.sqlite3').as_uri()+'?mode=ro',uri=True) as source:
                for key,targets in sorted(selected.items()):
                    n,w=source.execute('SELECT count(*),sum(multiplicity) FROM jobs WHERE symbol=? AND decision_ns=? AND is_put=?',key).fetchone()
                    if not n:raise ValueError('Pending cohort absent from frozen queue')
                    entries.append(dict(key=list(key),targets=sorted(targets),horizons=n,proposals=w))
            if entries:write(t/(sid+'.json'),entries)
            observations[sid]=dict(database=str(path),before_sha256=before,after_sha256=sha(path),
                recovery_originals=recovery,selected_cohorts=len(entries),selected_targets=sum(len(x['targets']) for x in entries),
                horizon_targets=sum(x['horizons']*len(x['targets']) for x in entries))
            count+=len(entries)
            for p in [wave/'progress.json',path.parent/'progress.json']:
                if p.exists():
                    try:d=json.loads(p.read_text())
                    except json.JSONDecodeError:d=dict(status='running',unreadable_previous_progress=True,previous_bytes=p.stat().st_size,previous_sha256=sha(p))
                    if d.get('status')=='running':
                        backup=t/'stale-progress'/sid;backup.mkdir(parents=True,exist_ok=True)
                        shutil.copy2(p,backup/('wave.json' if p.parent==wave else 'security.json'))
                        write(p,{**d,'status':'interrupted','recovery_plan':str(output)})
            lock.close()
        report=dict(securities=sum(v['selected_cohorts']>0 for v in observations.values()),selected_cohorts=count,
            selected_targets=sum(v['selected_targets'] for v in observations.values()),
            horizon_targets=sum(v['horizon_targets'] for v in observations.values()),full_execution_coverage=False,
            scope='Replay complete cohort/target memberships only where the preserved ledger emitted pending requests')
        write(t/'binding.json',dict(inputs=inputs,jobs=str(jobs),parent=str(parent),source_observations=observations))
        write(t/'report.json',report);receipt(t,dict(identity=identity(inputs),research_ready=False))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['parent','jobs','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();print(json.dumps(plan(a.parent,a.jobs,a.output),indent=2))
