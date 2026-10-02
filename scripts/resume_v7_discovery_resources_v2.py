"""Discovery resource revision preserving the existing frontier's progress path."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import resume_v7_compute_20260930 as previous
from scripts import finish_v7_required_inputs as original
from incubator.continual.storage import write
from nn_meta.v7.storage import sha

class Controller(original.Controller):
    def __init__(self):
        super().__init__('discovery')
        self.revision = dict(schema='v7-discovery-resources-v2', worker_ceiling=4,
            memory_high_mib=12288, memory_max_mib=14336,
            preserved_progress=str(original.RECOVERY / 'progress.json'),
            sources={str(ROOT / 'scripts' / name): sha(ROOT / 'scripts' / name) for name in
                     ['resume_v7_discovery_resources_v2.py', 'run_v7_execution_recovery_v2.py',
                      'v7_discovery_resources_v2.py', 'resume_v7_compute_20260930.py', 'lib/autosize.sh']})
        anchor = self.root / 'resource-revision-v2.json'
        if anchor.exists() and json.loads(anchor.read_text()) != self.revision:
            raise ValueError('Discovery resource revision changed')
        write(anchor, self.revision)

    def check(self):
        super().check()
        if any(sha(p) != digest for p, digest in self.revision['sources'].items()):
            raise ValueError('Discovery resource source changed')

    def discovery(self):
        while not original.terminal(json.loads((original.RECOVERY / 'progress.json').read_text()), 'discovery'):
            self.check()
            self.capacity()
            command = previous.discovery_command(4)
            command[2] = str(ROOT / 'scripts/run_v7_execution_recovery_v2.py')
            self.report('original_discovery', worker_ceiling=4, dynamic_admission=True)
            self.child = subprocess.Popen(command, cwd=ROOT)
            code = self.child.wait()
            self.child = None
            self.check()
            if code:
                raise RuntimeError('Discovery resource revision exited ' + str(code))
        self.report('full_original_discovery_complete')


def main():
    controller = Controller()
    try:
        controller.discovery()
    except InterruptedError:
        controller.report('stopped')
    except BaseException as exc:
        controller.report('blocked', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        if controller.child and controller.child.poll() is None:
            controller.child.terminate()
            controller.child.wait(timeout=60)


if __name__ == '__main__':
    main()
