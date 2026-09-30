#!/usr/bin/env python3
"""Resource-only V7 continuation revision; preserve existing scientific bindings."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from incubator.continual.storage import write
from nn_meta.v7.storage import sha
from scripts import finish_v7_required_inputs as original


def workers(mb, maximum, reserve):
    count = subprocess.check_output(['bash', '-c',
        'source scripts/lib/autosize.sh; autosize_workers "$1" "$2"',
        'v7-resumed-workers', str(mb), str(reserve)], cwd=ROOT, text=True)
    return min(maximum, max(1, int(count.strip())))


def discovery_command(count):
    v = ROOT / 'nn_meta/validation'
    command = [sys.executable, '-u', str(ROOT / 'scripts/run_v7_execution_recovery.py')]
    paths = dict(plan=v / 'v7-full-execution-plan-20260928',
        base_index=v / 'v7-frontier-quote-index-20260928-r4',
        entry_root=ROOT / 'nn_meta/data_v7/entry-campaign-20260927',
        references=v / 'v7-reference-reconciliation-20260928-full-r0',
        review=v / 'v7-reference-rename-review-20260928', hours=v / 'v7-dated-hours-20260927',
        blackouts=v / 'v7-contract-blackouts-20260928-approved',
        parent_state=original.ORIGINAL, state=original.RECOVERY)
    for key, path in paths.items():
        command += ['--' + key.replace('_', '-'), str(path)]
    return command + ['--workers', str(count), '--slice-seconds', '300', '--max-seconds', '21600']


class Controller(original.Controller):
    def __init__(self, mode):
        super().__init__(mode)
        self.resource_binding = dict(source=str(Path(__file__).resolve()), source_sha256=sha(__file__),
            original_binding=self.binding, discovery_memory_mib=8192, frontier_memory_mib=6144,
            discovery_worker_ceiling=2, quote_worker_ceiling=4, replay_worker_ceiling=1)
        target = self.root / 'resource-revision-20260930-focus.json'
        if target.exists() and json.loads(target.read_text()) != self.resource_binding:
            raise ValueError('Resource revision changed; preserve its bound source')
        write(target, self.resource_binding)

    def check(self):
        super().check()
        if sha(__file__) != self.resource_binding['source_sha256']:
            raise ValueError('Resource continuation source changed')

    def workers(self, mb, cap):
        # The unchanged producers admit at most four captures and one replay.
        maximum = 4 if mb == 1024 else cap
        return workers(mb, maximum, 16384)

    def discovery(self):
        self.wait_unit('healys-v7-discovery-20260930.service')
        while not original.terminal(json.loads((original.RECOVERY / 'progress.json').read_text()), 'discovery'):
            self.check()
            self.capacity()
            count = workers(3072, 2, 12288)
            self.report('original_discovery', workers=count)
            self.child = subprocess.Popen(discovery_command(count), cwd=ROOT)
            code = self.child.wait()
            self.child = None
            self.check()
            if code:
                raise RuntimeError('Original discovery exited ' + str(code))
        self.report('full_original_discovery_complete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['discovery', 'frontier'])
    args = parser.parse_args()
    controller = Controller(args.mode)
    try:
        getattr(controller, args.mode)()
    except InterruptedError:
        controller.report('stopped')
    except BaseException as exc:
        controller.report('blocked', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        if controller.child and controller.child.poll() is None:
            controller.child.terminate()
            try:
                controller.child.wait(timeout=60)
            except subprocess.TimeoutExpired:
                controller.child.kill()
                controller.child.wait()


if __name__ == '__main__':
    main()
