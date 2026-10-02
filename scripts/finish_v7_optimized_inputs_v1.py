#!/usr/bin/env python3
"""Adopt retained V7 discovery/replay with optimized, source-bound successors."""
import argparse
import fcntl
import json
from pathlib import Path
import signal
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import importlib.util
_spec=importlib.util.spec_from_file_location('_v7_optimized_base',ROOT/'scripts/finish_v7_required_inputs.py')
original=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(original)
from scripts.run_v7_optimized_campaign_v1 import read, SOURCES
from incubator.continual.storage import write
from nn_meta.v7.storage import sha,verify

OLD=original.STATE
STATE=original.V/'v7-required-inputs-20261002-perf-r0'
original.STATE=STATE
original.RECOVERY=STATE/'discovery-campaign'
original.ORIGINAL=original.RECOVERY


def save_config(path, value):
    if path.exists() and read(path)!=value:raise ValueError('Campaign configuration changed')
    write(path,value)


class Controller(original.Controller):
    def __init__(self,mode):
        self.mode=mode;self.root=STATE/mode;self.root.mkdir(parents=True,exist_ok=True)
        self.locks=[]
        for directory in [self.root,OLD/mode]:
            lock=(directory/'lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);self.locks.append(lock)
        self.stopping=False;self.child=None
        sources=dict(read(OLD/mode/'binding.json')['sources'])
        for p in [*SOURCES,'scripts/finish_v7_optimized_inputs_v1.py']:
            sources[str(ROOT/p)]=sha(ROOT/p)
        self.binding=dict(schema='v7-optimized-supervisor-v1',mode=mode,overall_time_limit=None,
            sources=sources,predecessor_binding_sha256=sha(OLD/mode/'binding.json'),
            adoption_sha256=sha(STATE/'adoption.json'))
        anchor=self.root/'binding.json'
        if anchor.exists() and read(anchor)!=self.binding:raise ValueError('Supervisor changed')
        self.check();write(anchor,self.binding)
        signal.signal(signal.SIGTERM,self.stop);signal.signal(signal.SIGINT,self.stop)

    def check(self):
        super().check()
        if sha(STATE/'adoption.json')!=self.binding['adoption_sha256']:
            raise ValueError('Adoption changed')

    def discovery(self):
        while not original.terminal(read(original.RECOVERY/'progress.json'),'discovery'):
            self.run('run_v7_optimized_campaign_v1.py','--state',original.RECOVERY,
                '--config',STATE/'discovery-config.json','--workers',4,'--slice-seconds',600,'--max-seconds',21600)
        self.report('full_original_discovery_complete')

    def replay(self,parent,plan,quotes,references,campaign):
        if campaign.name=='initial-replay':
            retained=OLD/'initial-replay'
            if not original.terminal(read(retained/'progress.json'),'replay'):
                raise ValueError('Expected completed initial replay')
            return retained
        if not plan.exists():
            self.run('plan_v7_pending_replay.py','--parent',parent,'--jobs',original.JOBS,'--output',plan)
        verify(plan)
        report=read(plan/'report.json')
        if not report['securities']:return None
        predecessor=OLD/'epochs'/campaign.parent.name/'replay'
        args={'plan':str(original.JOBS),'replay-plan':str(plan.resolve()),'base-index':str(quotes.resolve()),
            'entry-root':str(original.D/'entry-campaign-20260927'),'references':str(references.resolve()),
            'review':str(original.V/'v7-reference-rename-review-20260928'),
            'hours':str(original.V/'v7-dated-hours-20260927'),'blackouts':str(original.POLICY)}
        config=dict(mode='replay',arguments=args,securities=sorted(p.stem for p in plan.glob('BBG*.json')),
            parent=str(predecessor) if predecessor.exists() else None,
            exclusive_roots=[str(predecessor)] if predecessor.exists() else [])
        config_path=campaign.parent/'optimized-replay-config.json';save_config(config_path,config)
        while True:
            meter=campaign/'progress.json'
            if meter.exists() and original.terminal(read(meter),'replay'):return campaign
            self.run('run_v7_optimized_campaign_v1.py','--state',campaign,'--config',config_path,
                '--workers',1,'--slice-seconds',600,'--max-seconds',14400)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['discovery','frontier']);a=p.parse_args()
    c=Controller(a.mode)
    try:getattr(c,a.mode)()
    except InterruptedError:c.report('stopped')
    except BaseException as exc:
        c.report('blocked',error=f'{type(exc).__name__}: {exc}');raise
    finally:
        if c.child and c.child.poll() is None:
            c.child.terminate();c.child.wait(timeout=1200)

if __name__=='__main__':main()
