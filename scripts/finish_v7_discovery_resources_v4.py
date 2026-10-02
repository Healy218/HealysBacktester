#!/usr/bin/env python3
"""Resource-only discovery successor; retain the selected optimized wave contracts."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.finish_v7_optimized_inputs_v1 import Controller as PriorController,STATE,original
from nn_meta.v7.storage import sha
from incubator.continual.storage import write


class Controller(PriorController):
    def __init__(self):
        super().__init__('discovery')
        self.resource_sources={str(ROOT/p):sha(ROOT/p) for p in [
            'scripts/finish_v7_discovery_resources_v4.py','scripts/run_v7_optimized_campaign_v3.py',
            'scripts/v7_discovery_resources_v3.py','scripts/v7_discovery_resources_v4.py']}
        target=self.root/'resources-v4.json'
        if target.exists() and json.loads(target.read_text())!=self.resource_sources:raise ValueError('Resource source changed')
        write(target,self.resource_sources)

    def check(self):
        super().check()
        if any(sha(p)!=h for p,h in getattr(self,'resource_sources',{}).items()):raise ValueError('Resource source changed')

    def discovery(self):
        while not original.terminal(json.loads((original.RECOVERY/'progress.json').read_text()),'discovery'):
            self.run('run_v7_optimized_campaign_v3.py','--state',original.RECOVERY,
                '--config',STATE/'discovery-config.json','--workers',12,'--slice-seconds',300,'--max-seconds',21600)
        self.report('full_original_discovery_complete')


def main():
    c=Controller()
    try:c.discovery()
    except InterruptedError:c.report('stopped')
    except BaseException as exc:
        c.report('blocked',error=f'{type(exc).__name__}: {exc}');raise
    finally:
        if c.child and c.child.poll() is None:c.child.terminate();c.child.wait(timeout=1200)

if __name__=='__main__':main()
