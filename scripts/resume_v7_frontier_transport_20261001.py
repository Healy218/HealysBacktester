#!/usr/bin/env python3
"""One explicit restart of the stopped September 30 HTTP-502 capture pass."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from incubator.continual.storage import sha,write
from scripts.resume_v7_compute_20260930 import Controller as ResourceController

STATE=ROOT/'nn_meta/validation/v7-frontier-restart-20261001-r0'


def retryable(doc):
    failures=doc.get('failed_batches',[])
    return (doc.get('status')=='draining' and doc.get('active_batches')==0 and
            doc.get('error') is None and len(failures)==2 and
            all(f.get('error_type')=='TickDataError' and f.get('reason')=='Massive ticks HTTP 502'
                for f in failures))


class Controller(ResourceController):
    def __init__(self):
        super().__init__('frontier')
        self.recovery=dict(source_sha256=sha(__file__),authorization_sha256=sha(STATE/'authorization.json'))
        path=STATE/'binding.json'
        if path.exists() and json.loads(path.read_text())!=self.recovery:
            raise ValueError('Transport recovery binding changed')
        write(path,self.recovery)

    def check(self):
        super().check()
        if sha(__file__)!=self.recovery['source_sha256'] or sha(STATE/'authorization.json')!=self.recovery['authorization_sha256']:
            raise ValueError('Transport recovery source or authorization changed')

    def capture(self,snapshot,quotes,state,output,initial=False):
        authorization=json.loads((STATE/'authorization.json').read_text())
        meter=state/'progress.json'
        if initial and str(meter)==authorization['progress'] and meter.exists() and sha(meter)==authorization['progress_sha256']:
            doc=json.loads(meter.read_text())
            if not retryable(doc):raise ValueError('Failure is outside the authorized HTTP-502 retry')
            if (STATE/'retry-started.json').exists():
                raise RuntimeError('Previous explicit retry published no new checkpoint; inspect before another restart')
            self.wait_unit('healys-v7-frontier-20260930.service')
            history=state/'supervised-passes';history.mkdir(exist_ok=True)
            number=len(list(history.glob('*.json')))+1
            attempt=dict(previous=doc,created_at=datetime.now(timezone.utc).isoformat(),
                         recovery=str(STATE),authorization_sha256=self.recovery['authorization_sha256'])
            write(history/f'{number:05d}.json',attempt)
            write(STATE/'retry-started.json',dict(attempt=number,**attempt))
            # Unchanged producer verifies every completed pack and queues only
            # absent seals. Historical failures/attempt receipts remain intact.
            self.run('capture_v7_recovery_frontier.py','capture','--plan',snapshot,'--previous-index',quotes,
                     '--output',output,'--state',state,'--index-output',state/f'index-{number:05d}',
                     '--workers',self.workers(1024,2),'--max-seconds',14400)
        return super().capture(snapshot,quotes,state,output,initial=initial)


def main():
    controller=Controller()
    try:
        controller.frontier()
    except InterruptedError:
        controller.report('stopped')
    except BaseException as exc:
        controller.report('blocked',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        if controller.child and controller.child.poll() is None:
            controller.child.terminate()
            controller.child.wait(timeout=60)


if __name__=='__main__':main()
