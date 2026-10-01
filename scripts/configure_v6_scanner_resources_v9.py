"""Install only the versioned V6 paper scanner resource allowance."""
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
REVISION = STATE/'runtime-revisions/scanner-resources-v9-20261001'
REL = 'scripts/run_v6_alpaca_scanner_v9.sh'
UNIT_REL = 'healys-v6-alpaca-scanner.service.d/90-resource-v9.conf'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    from scripts.run_v6_alpaca_runtime_v5 import save
    with (STATE/'scanner-dispatch.lock').open('a') as scan, (STATE/'bridge.lock').open('a') as bridge:
        # A scheduled scan may start while host approval is pending. Let it
        # finish; never replace the resource manifest during an active scan.
        fcntl.flock(scan, fcntl.LOCK_EX)
        fcntl.flock(bridge, fcntl.LOCK_EX)
        path = STATE/'paper-restart.json'
        prior = json.loads(path.read_text())
        if prior.get('scanner_resource_policy') == 'memory-aware-16g-v9':
            raise ValueError('Resource revision already installed; inspect instead of overwriting')
        for name, digest in prior['bridge_runtime_sha256'].items():
            if sha(ROOT/name) != digest:
                raise ValueError('Existing admitted bridge changed: '+name)
        REVISION.mkdir(parents=True, exist_ok=False)
        shutil.copy2(path, REVISION/'paper-restart.json')
        result = subprocess.run(['systemctl','--user','cat','healys-v6-alpaca-scanner.service'],
                                check=True, capture_output=True, text=True)
        (REVISION/'scanner-unit.txt').write_text(result.stdout)
        target = Path.home()/'.config/systemd/user'/UNIT_REL
        if target.exists():
            raise ValueError('New resource drop-in already exists')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/'deploy/systemd'/UNIT_REL, target)
        updated = dict(prior, bridge_runtime_sha256={**prior['bridge_runtime_sha256'],REL:sha(ROOT/REL)},
                       scanner_resource_policy='memory-aware-16g-v9')
        save(path, updated)
        subprocess.run(['systemctl','--user','daemon-reload'],check=True)
        evidence = ROOT/'nn_meta/validation/v6-paper-vintage-20261001-r0/scanner-resources-v9.json'
        save(evidence,dict(prior_manifest_sha256=sha(REVISION/'paper-restart.json'),
            current_manifest_sha256=sha(path), backup=str(REVISION), dropin=str(target),
            resource_policy=updated['scanner_resource_policy'], launcher_sha256=sha(ROOT/REL),
            model_release_unchanged=True, execution_policy_unchanged=True))
        print(evidence)


if __name__ == '__main__':
    main()
