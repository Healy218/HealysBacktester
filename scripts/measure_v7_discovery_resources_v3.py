#!/usr/bin/env python3
"""Read-only production throughput observations after resource adoption."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.lab_hourly_watch import v7_work
from scripts.v7_discovery_resources_v3 import admission,anon_mib
from incubator.continual.storage import write
EVIDENCE=ROOT/'nn_meta/validation/v7-discovery-resources-20261002-r3'
STATE=ROOT/'nn_meta/validation/v7-required-inputs-20261002-perf-r0'
PAPER=Path('/home/healy/Coding/HealysV6/nn_meta/live/v6_alpaca_paper')


def sample():
    w=v7_work({})['original_discovery'];runtime=w['runtime']
    result=dict(observed_at=datetime.now(timezone.utc).isoformat(),
        cohorts=w['cohorts_processed'],assessments=w['horizon_targets_assessed'],
        finished_securities=w['terminal_securities_including_empty'],partial_securities=w['partial_securities'],
        active_workers=len(runtime.get('active_securities',[])),runtime=runtime,admission=admission(12))
    for name in ['scanner-dispatch-status','status','position-monitor-status']:
        d=json.loads((PAPER/(name+'.json')).read_text())
        result[name]={k:v for k,v in d.items() if k in ['checked_at','status','phase','elapsed_seconds','errors','detection_errors']}
    cg=Path('/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice/healys-v7-required-discovery-20260930.service')
    for name in ['memory.events','memory.pressure','cpu.stat']:
        if (cg/name).exists():result[name]=(cg/name).read_text()
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seconds',type=int,default=900);a=p.parse_args()
    target=EVIDENCE/'measurement.json'
    if target.exists():raise ValueError('Measurement already exists; preserve it')
    total=0
    for path in (ROOT/'nn_meta/validation/v7-full-execution-plan-20260928/jobs').glob('*/report.json'):
        r=json.loads(path.read_text());b=json.loads((path.parent/'binding.json').read_text())
        total+=r['distinct_horizons']*len(b['targets'])
    samples=[];began=time.monotonic()
    while True:
        samples.append(sample());last=samples[-1]
        write(target,dict(total_assessments=total,samples=samples))
        print(json.dumps({k:last[k] for k in ['observed_at','cohorts','assessments','finished_securities','active_workers']}),flush=True)
        if last['runtime'].get('failed_securities') or last['runtime'].get('error'):raise RuntimeError('Discovery failed during measurement')
        if time.monotonic()-began>=a.seconds:break
        time.sleep(min(30,max(0,a.seconds-(time.monotonic()-began))))
    start,end=samples[0],samples[-1]
    intervals=[]
    for first,last in zip(samples,samples[1:]):
        secs=(datetime.fromisoformat(last['observed_at'])-datetime.fromisoformat(first['observed_at'])).total_seconds()
        intervals.append((last['assessments']-first['assessments'])*3600/secs)
    hours=(datetime.fromisoformat(end['observed_at'])-datetime.fromisoformat(start['observed_at'])).total_seconds()/3600
    rate=(end['assessments']-start['assessments'])/hours
    write(EVIDENCE/'measurement-summary.json',dict(observed_at=end['observed_at'],minutes=hours*60,
        assessments_added=end['assessments']-start['assessments'],cohorts_added=end['cohorts']-start['cohorts'],
        assessments_per_hour=rate,total_assessments=total,remaining_assessments=total-end['assessments'],
        constant_rate_remaining_days=(total-end['assessments'])/rate/24 if rate else None,
        active_worker_range=[min(x['active_workers'] for x in samples),max(x['active_workers'] for x in samples)],
        interval_rates=intervals))

if __name__=='__main__':main()
