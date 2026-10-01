"""Build and validate a new October 1 paper-input vintage; publish explicitly."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT.parent / 'HealysV6'
sys.path.insert(0, str(FROZEN))
from nn_meta.live.v6_market import read, save, utcnow
from nn_meta.live.v6_release import sha, verify_release

STATE = FROZEN / 'nn_meta/live/v6_server'
PAPER = FROZEN / 'nn_meta/live/v6_alpaca_paper'
EVIDENCE = ROOT / 'nn_meta/validation/v6-paper-vintage-20261001-r0'
OUTPUT = ROOT / 'nn_meta/live/v6_server/data/2026-09-30-vintage-20261001'
RELEASE = FROZEN / 'deploy/v6/releases/v6-cash-repair-20260913'
ANCHOR = '3bc974679fff04044002f833cbb4c9246f63fd4d9370c04985f5f6ca7597764f'


def verify_inputs():
    from dotenv import load_dotenv
    from nn_meta.live.v6_forward_inputs import ForwardData
    load_dotenv(ROOT / '.env')
    verify_release(RELEASE, ANCHOR)
    data = ForwardData(OUTPUT, expected_sha256=sha(OUTPUT/'manifest.json'), release=RELEASE, anchor=ANCHOR)
    data.update(utcnow(), capture=EVIDENCE/'stock-captures')
    old = read(EVIDENCE/'before-index.json')
    if sha(Path(old['path'])/'manifest.json') != old['sha256']:
        raise ValueError('Original snapshot changed')
    return dict(observed_at=utcnow().isoformat(), status='validated',
                manifest_sha256=sha(OUTPUT/'manifest.json'), symbols=len(data.spec['symbols']),
                through=data.document['through'], market_receipts=data.market_receipts,
                original_manifest_unchanged=True, model_sha256=data.document['model_sha256'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'publish'])
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if args.action == 'prepare':
        before = EVIDENCE/'before-index.json'
        if not before.exists():
            save(before, read(STATE/'data-index.json'))
            save(EVIDENCE/'before-paper-manifest.json', read(PAPER/'paper-restart.json'))
        old = read(before)
        if old['through'] != '2026-09-30' or sha(Path(old['path'])/'manifest.json') != old['sha256']:
            raise ValueError('Unexpected original snapshot')
        if not (OUTPUT/'manifest.json').exists():
            # Reuse only sealed option aggregates; rebuild adjusted histories and
            # their derived context with the unchanged frozen producer.
            manifest = read(Path(old['path'])/'manifest.json')
            for receipt in manifest['new_option_daily']:
                source = Path(old['path'])/receipt['path']
                if sha(source) != receipt['sha256']:
                    raise ValueError('Option context capture changed')
                target = OUTPUT/receipt['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    os.link(source, target)
                if sha(target) != receipt['sha256']:
                    raise ValueError('Reused context differs')
            from scripts.prepare_v6_forward_data import prepare
            prepare(argparse.Namespace(source=ROOT/'nn_meta/data_candidates/audit-repair-20260905-final/cache',
                    release=RELEASE, anchor=ANCHOR, output=OUTPUT, through='2026-09-30', env=ROOT/'.env'))
        result = verify_inputs()
        save(EVIDENCE/'validation.json', result)
    else:
        # The routine refresh producer uses this lock. Compare-and-publish only
        # while the selected prior-session pointer still matches our baseline.
        with (STATE/'.refresh.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if read(STATE/'data-index.json') != read(EVIDENCE/'before-index.json'):
                raise ValueError('Data pointer changed during repair; review before publication')
            result = verify_inputs()
            from scripts.v6_forward_ops import publish_data
            result['published_index'] = publish_data(OUTPUT, RELEASE, ANCHOR, STATE/'data-index.json')
            save(EVIDENCE/'published.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
