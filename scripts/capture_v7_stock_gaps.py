"""Capture explicitly reviewed stock/day gaps without replacing existing history."""
from pathlib import Path
import argparse
from datetime import date, timedelta
import fcntl
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import worker_pool
    from nn_meta.v7.storage import sha
    from scripts.download_v7_data import acquire, save
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--requests', type=Path, required=True)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, required=True)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        raise ValueError('Use one to four workers')
    base, output = args.base.resolve(), args.output.resolve()
    if output.parent != base.parent or not (output.parent / 'quota.json').exists():
        raise ValueError('Existing shared acquisition quota required')
    calendar = json.loads((base / 'calendar.json').read_text())
    days = {s['date'] for s in calendar['sessions']}
    requests = json.loads(args.requests.read_text())
    work, seen = [], set()
    for row in requests:
        symbol, day = row['symbol'], row['date']
        if not re.fullmatch(r'[A-Z][A-Z0-9.]{0,14}', symbol) or day not in days:
            raise ValueError('Invalid symbol or uncaptured session')
        if (symbol, day) in seen:
            raise ValueError('Duplicate requested stock day')
        seen.add((symbol, day))
        end = (date.fromisoformat(day) + timedelta(days=1)).isoformat()
        for adjustment in ('raw', 'all'):
            work.append({'kind': 'stock', 'symbol': symbol, 'adjustment': adjustment,
                         'start': day + 'T00:00:00Z', 'end': end + 'T00:00:00Z',
                         'key': f'stock_1m/{adjustment}/{symbol}/{day}'})
    sources = {name: sha(ROOT / name) for name in
               ('scripts/capture_v7_stock_gaps.py', 'scripts/download_v7_data.py')}
    scope = {'schema': 'v7-explicit-stock-gap-capture-v1', 'requests': requests,
             'requests_sha256': sha(args.requests), 'sources': sources,
             'calendar_sha256': sha(base / 'calendar.json'), 'research_ready': False}
    output.mkdir(parents=True, exist_ok=True)
    with (output.parent / '.acquisition.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / 'acquisition.json').exists() and json.loads((output / 'acquisition.json').read_text()) != scope:
            raise ValueError('Capture scope changed; use a fresh output directory')
        save(output / 'acquisition.json', scope)
        state = {'total': len(work), 'completed': 0, 'failed': 0, 'research_ready': False}
        with worker_pool(args.workers, threads=1) as pool:
            for first in range(0, len(work), args.workers):
                if any(sha(ROOT / p) != digest for p, digest in sources.items()):
                    raise ValueError('Capture source changed')
                futures = [(task, pool.submit(acquire, str(output), task, 100))
                           for task in work[first:first + args.workers]]
                for task, future in futures:
                    try:
                        result = future.result()
                        state['completed'] += 1
                    except Exception as exc:
                        state['failed'] += 1
                        result = {'key': task['key'], 'error': str(exc)}
                    print(json.dumps(result), flush=True)
                save(output / 'status.json', state)
                if state['failed']:
                    break
        if state['failed']:
            raise RuntimeError('Explicit stock gap capture incomplete')


if __name__ == '__main__':
    main()
