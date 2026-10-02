"""Install an explicitly versioned discovery scheduler, preserving wave seals."""
import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from incubator.continual.storage import write
from nn_meta.v7.storage import sha
from scripts import finish_v7_required_inputs as original
from scripts.v7_discovery_resources_v2 import worker_limit

UNIT = 'healys-v7-required-discovery-20260930.service'
EVIDENCE = ROOT / 'nn_meta/validation/v7-discovery-resources-20261002-r0'


def control(*args):
    return subprocess.check_output(['systemctl', '--user', *args], text=True)


def preflight():
    for anchor in [original.RECOVERY / 'declaration.json', original.STATE / 'discovery/binding.json']:
        doc = json.loads(anchor.read_text())
        for path, digest in doc.get('inputs', doc.get('sources', {})).items():
            if sha(path) != digest:
                raise ValueError('Existing bound source changed: ' + path)
    for name in ['resume_v7_discovery_resources_v2.py', 'run_v7_execution_recovery_v2.py',
                 'v7_discovery_resources_v2.py']:
        source = ROOT / 'scripts' / name
        compile(source.read_text(), str(source), 'exec')
    return dict(observed_at=datetime.now(timezone.utc).isoformat(), admitted_now=worker_limit(),
                wave_declarations={str(p): sha(p) for p in (original.ORIGINAL / 'waves').glob('*/declaration.json')},
                predecessor_sha256=sha(original.RECOVERY / 'declaration.json'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    before = preflight()
    if not args.apply:
        print(json.dumps(dict(preflight='passed', admitted_now=before['admitted_now'],
                             preserved_wave_declarations=len(before['wave_declarations']))))
        return
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    lock = (EVIDENCE / 'install.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    target = Path('/run/user') / str(__import__('os').getuid()) / 'systemd/user' / (UNIT + '.d') / '99-discovery-resources-v2.conf'
    if target.exists() or (EVIDENCE / 'before.json').exists():
        raise ValueError('Resource revision already installed or attempted; inspect retained evidence')
    unit_before = control('cat', UNIT)
    if 'resume_v7_compute_20260930.py discovery' not in unit_before:
        raise ValueError('Unexpected discovery deployment')
    before['unit'] = unit_before
    before['recovery'] = json.loads((original.RECOVERY / 'progress.json').read_text())
    before['supervisor'] = json.loads((original.STATE / 'discovery/progress.json').read_text())
    write(EVIDENCE / 'before.json', before)
    # KillMode=mixed delivers TERM to the supervisor; the existing controller
    # closes its workers and preserves committed SQLite cohorts and wave locks.
    control('stop', UNIT)
    stopped = json.loads((original.RECOVERY / 'progress.json').read_text())
    write(EVIDENCE / 'stopped.json', stopped)
    original.terminal(stopped, 'discovery')  # rejects failures before handover
    for path, digest in before['wave_declarations'].items():
        if sha(path) != digest:
            raise ValueError('Wave declaration changed during handover: ' + path)
    if sha(original.RECOVERY / 'declaration.json') != before['predecessor_sha256']:
        raise ValueError('Predecessor seal changed during handover')
    source = ROOT / 'deploy/systemd' / (UNIT + '.d') / target.name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text())
    control('daemon-reload')
    control('start', UNIT)
    write(EVIDENCE / 'deployment.json', dict(observed_at=datetime.now(timezone.utc).isoformat(),
          dropin=str(target), dropin_sha256=sha(target), before_sha256=sha(EVIDENCE / 'before.json'),
          wave_declarations_preserved=True,
          service=control('show', UNIT, '-p', 'ActiveState', '-p', 'SubState', '-p', 'ExecStart',
                          '-p', 'MemoryHigh', '-p', 'MemoryMax', '-p', 'CPUQuotaPerSecUSec')))
    print((EVIDENCE / 'deployment.json').read_text())


if __name__ == '__main__':
    main()
