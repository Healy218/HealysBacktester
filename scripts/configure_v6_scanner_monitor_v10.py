"""Admit the V6 paper consumer with concurrent, bounded quote monitoring."""
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
STATE = ROOT.parent/'HealysV6/nn_meta/live/v6_alpaca_paper'
REVISION = STATE/'runtime-revisions/scanner-monitor-v10-20261001'
RELS = ('scripts/run_v6_alpaca_scanner_v10.sh', 'scripts/run_v6_alpaca_scanner_v10.py',
        'scripts/run_v6_forward_resilient_v1.py')
UNIT_REL = 'healys-v6-alpaca-scanner.service.d/95-monitor-v10.conf'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    from scripts.run_v6_alpaca_runtime_v5 import save
    with (STATE/'scanner-dispatch.lock').open('a') as scan, (STATE/'bridge.lock').open('a') as bridge:
        # A scheduled scan may start while host approval is pending. Let it
        # finish; never replace the admitted manifest during an active scan.
        fcntl.flock(scan, fcntl.LOCK_EX)
        fcntl.flock(bridge, fcntl.LOCK_EX)
        path = STATE/'paper-restart.json'
        prior = json.loads(path.read_text())
        if prior.get('scanner_monitor_policy') == 'concurrent-quote-retry-v1':
            raise ValueError('Monitor revision already installed; inspect instead of overwriting')
        for name, digest in prior['bridge_runtime_sha256'].items():
            if sha(ROOT/name) != digest:
                raise ValueError('Existing admitted bridge changed: '+name)
        frozen = Path(prior['old_state']).parents[2]
        activation = json.loads((STATE/'activation.json').read_text())
        for name, digest in activation['runtime_sha256'].items():
            if sha(frozen/name) != digest:
                raise ValueError('Frozen runtime changed: '+name)
        if sha(frozen/'scripts/run_v6_forward.py') != 'cfdee72d1a8ee9b386825a255412007bc108bbe73b5b2f2b001afcd9398137c2':
            raise ValueError('Unexpected consumer parent')
        REVISION.mkdir(parents=True, exist_ok=False)
        shutil.copy2(path, REVISION/'paper-restart.json')
        result = subprocess.run(['systemctl','--user','cat','healys-v6-alpaca-scanner.service'],
                                check=True, capture_output=True, text=True)
        (REVISION/'scanner-unit.txt').write_text(result.stdout)
        target = Path.home()/'.config/systemd/user'/UNIT_REL
        if target.exists():
            raise ValueError('New monitor drop-in already exists')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/'deploy/systemd'/UNIT_REL, target)
        updated = dict(prior,
            bridge_runtime_sha256={**prior['bridge_runtime_sha256'], **{rel:sha(ROOT/rel) for rel in RELS}},
            scanner_monitor_policy='concurrent-quote-retry-v1',
            scanner_consumer_lineage=dict(
                frozen_scanner_sha256='cfdee72d1a8ee9b386825a255412007bc108bbe73b5b2f2b001afcd9398137c2',
                consumer='scripts/run_v6_forward_resilient_v1.py',
                preserved='frozen modules, model, inputs, pricing, deadlines and broker execution'))
        save(path, updated)
        subprocess.run(['systemctl','--user','daemon-reload'],check=True)
        evidence = ROOT/'nn_meta/validation/v6-paper-quotes-20261001-r0/deployment.json'
        save(evidence,dict(prior_manifest_sha256=sha(REVISION/'paper-restart.json'),
            current_manifest_sha256=sha(path), backup=str(REVISION), dropin=str(target),
            monitor_policy=updated['scanner_monitor_policy'], sources={rel:sha(ROOT/rel) for rel in RELS},
            model_release_unchanged=True, execution_policy_unchanged=True))
        print(evidence)


if __name__ == '__main__':
    main()
