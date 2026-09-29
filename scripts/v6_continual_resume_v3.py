#!/usr/bin/env python3
"""Resume an unfinished full catch-up before advancing to a newer session."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def unfinished_session(root):
    path = Path(root) / 'latest-run.json'
    if not path.exists():
        return None
    run = json.loads(path.read_text())
    if run['scope'] != 'full_universe':
        raise ValueError('selected production research root contains a pilot')
    if run['status'] in {'candidate_frozen', 'candidate_already_frozen', 'awaiting_matured_labels'}:
        return None
    return run['through']


def resume_config(config, through):
    """A later data-index publication cannot change an unfinished run's snapshot."""
    declaration = Path(config['root']) / 'runs' / through / 'declaration.json'
    if not declaration.exists():
        return config
    run = json.loads(declaration.read_text())
    if run['through'] != through:
        raise ValueError('resume declaration date differs')
    return {**config, 'bootstrap_snapshot': {
        'path': run['snapshot'], 'sha256': run['snapshot_sha256'], 'through': through,
    }}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record-exit', action='store_true')
    args = parser.parse_args()
    config = json.loads((ROOT / 'deploy/incubator-continual-v6-r3.json').read_text())
    root = Path(config['root'])
    if args.record_exit:
        sys.path.insert(0, str(ROOT))
        from datetime import datetime, timezone
        from incubator.continual.storage import write
        write(root / 'service-exit.json', {
            'observed_at': datetime.now(timezone.utc).isoformat(),
            'service_result': os.environ.get('SERVICE_RESULT'),
            'exit_code': os.environ.get('EXIT_CODE'),
            'exit_status': os.environ.get('EXIT_STATUS'),
            'note': 'Service receipt; candidate completion is established by sealed artifacts.',
        })
        return
    through = unfinished_session(root)
    command = ['/usr/bin/bash', str(ROOT / 'scripts/run_v6_continual_v3.sh'),
               '--max-seconds', '43200']
    if through:
        command += ['--through', through]
        sys.path.insert(0, str(ROOT))
        from incubator.continual.storage import identity, write
        resumed = resume_config(config, through)
        path = root / 'invocations' / (identity(resumed) + '.json')
        if path.exists() and json.loads(path.read_text()) != resumed:
            raise ValueError('resume configuration changed')
        if not path.exists():
            write(path, resumed)
        command += ['--config', str(path)]
    os.chdir(ROOT)
    os.execv(command[0], command)


if __name__ == '__main__':
    main()
