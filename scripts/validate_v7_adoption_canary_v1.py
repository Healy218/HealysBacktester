#!/usr/bin/env python3
"""Compare bounded successor-controller output against unchanged baseline producers."""
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.measure_v7_wave_v1 import digest_database,execute,command
from nn_meta.v7.storage import sha
from incubator.continual.storage import write
from scripts.run_v7_optimized_campaign_v1 import read
STATE=ROOT/'nn_meta/validation/v7-required-inputs-20261002-perf-r0'
OUT=STATE/'canary-validation'


def main():
    OUT.mkdir(exist_ok=True)
    report={}
    cases=[('discovery-small',STATE/'discovery-campaign',STATE/'discovery-config.json','BBG000C3HSR0'),
           ('discovery-prefix',STATE/'discovery-campaign',STATE/'discovery-config.json','BBG000BB5006'),
           ('replay-prefix',STATE/'epochs/00001/replay',STATE/'epochs/00001/optimized-replay-config.json','BBG000BB5006')]
    for label,campaign,config_path,sid in cases:
        config=read(config_path);parent=Path(config['parent'])/'waves'/sid;candidate=campaign/'revisions'/sid
        if not (candidate/'progress.json').exists():raise ValueError('Canary not yet published')
        inherit=read(candidate/'inherited-checkpoint.json')
        parent_files=inherit['parent_files']
        if any(sha(parent/'securities'/sid/name)!=digest for name,digest in parent_files.items()):raise ValueError('Original checkpoint changed')
        before=read(parent/'progress.json')['cohorts_discovered'];after=read(candidate/'progress.json')['cohorts_discovered']
        if after-before!=40:raise ValueError('Unexpected canary scope')
        destination=OUT/label
        if destination.exists():raise ValueError('Validation destination already exists')
        subprocess.run(['cp','-a','--reflink=always','--',str(parent),str(destination)],check=True)
        script='discover_v7_execution_wave_v2.py' if config['mode']=='discovery' else 'replay_v7_pending_wave.py'
        result=execute(command(config['arguments'],script,destination,sid,count=40),OUT/(label+'.log'))
        if result['exit_code']:raise ValueError('Baseline failed: '+label)
        expected=digest_database(destination/'securities'/sid/'wave.sqlite3')
        actual=digest_database(candidate/'securities'/sid/'wave.sqlite3')
        equal=expected==actual
        report[label]=dict(equal=equal,inherited_cohorts=before,new_cohorts=40,tables=actual,
            independent_inodes=(parent/'securities'/sid/'wave.sqlite3').stat().st_ino!=(candidate/'securities'/sid/'wave.sqlite3').stat().st_ino,
            parent_files_unchanged=True,baseline=result)
        write(OUT/'parity.json',report)
        if not equal:raise ValueError('Scientific parity failed: '+label)
        print(label,'exact parity',flush=True)
    write(OUT/'complete.json',dict(all_equal=True,cases=3,new_discovery_cohorts=80,new_replay_cohorts=40,
        parity_sha256=sha(OUT/'parity.json')))

if __name__=='__main__':main()
