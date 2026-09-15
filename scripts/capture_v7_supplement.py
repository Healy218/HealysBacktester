"""Acquire a historical candidate stock superset without resetting the shared quota."""
from pathlib import Path
import argparse
import fcntl
import json
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import worker_pool
    from nn_meta.v7.storage import sha
    from scripts.download_v7_data import acquire, tasks, save, CapacityPause
    ap = argparse.ArgumentParser(description=__doc__)
    for key in ('symbols', 'base', 'output'):
        ap.add_argument('--' + key, type=Path, required=True)
    ap.add_argument('--workers', type=int, required=True)
    ap.add_argument('--include-existing', action='store_true', help='Capture a fresh repair source for explicitly listed roots')
    ap.add_argument('--start')
    ap.add_argument('--end')
    args = ap.parse_args()
    if not 1 <= args.workers <= 4:
        raise ValueError('Use one to four bounded acquisition workers')
    output = args.output.resolve()
    base = args.base.resolve()
    if output.parent != base.parent or not (output.parent / 'quota.json').exists():
        raise ValueError('Supplement requires the existing initialized shared quota root')
    calendar_path = base / 'calendar.json'
    calendar = json.loads(calendar_path.read_text())
    start, end = args.start or calendar['coverage_start'], args.end or calendar['coverage_end']
    from datetime import date
    if (date.fromisoformat(start).isoformat() != start or date.fromisoformat(end).isoformat() != end
            or not calendar['coverage_start'] <= start <= end <= calendar['coverage_end']):
        raise ValueError('Acquisition dates must stay within the captured calendar')
    symbols = sorted(set(args.symbols.read_text().split()))
    # Exchange spelling only. No company-renaming or liquidity alias inference.
    symbols = ['BRK.B' if s == 'BRKB' else s for s in symbols]
    existing = {p.name for p in (base / 'stock_1m/raw').iterdir() if p.is_dir()}
    if not args.include_existing:
        symbols = [s for s in symbols if s not in existing]
    scope = {'schema': 'v7-historical-stock-supplement-v1', 'symbols': symbols,
             'candidate_symbols_sha256': sha(args.symbols), 'calendar_sha256': sha(calendar_path),
             'source_sha256': {p: sha(ROOT / p) for p in ('scripts/capture_v7_supplement.py', 'scripts/download_v7_data.py')},
             'warmup_start': start, 'end': end, 'include_existing': args.include_existing,
             'research_ready': False, 'scope_policy': 'candidate superset; identity/eligibility admission remains separate'}
    output.mkdir(parents=True, exist_ok=True)
    with (output.parent / '.acquisition.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / 'acquisition.json').exists() and json.loads((output / 'acquisition.json').read_text()) != scope:
            raise ValueError('Supplement scope/source changed; use a new output directory')
        save(output / 'acquisition.json', scope)
        save(output / 'calendar.json', calendar)
        work = list(tasks(symbols, calendar['sessions'], start, end, ['stock']))
        state = {'status': 'running', 'symbols': len(symbols), 'total': len(work), 'completed': 0,
                 'failed': 0, 'research_ready': False, 'last_results': []}
        save(output / 'status.json', state)
        began = time.perf_counter()
        with worker_pool(args.workers, threads=1) as pool:
            for first in range(0, len(work), args.workers):
                if any(sha(ROOT / p) != digest for p, digest in scope['source_sha256'].items()):
                    raise ValueError('Acquisition source changed during the run')
                group = work[first:first + args.workers]
                futures = [(task, pool.submit(acquire, str(output), task, 100)) for task in group]
                paused = False
                for task, future in futures:
                    try:
                        result = future.result()
                        state['completed'] += 1
                    except CapacityPause as exc:
                        result = {'key': task['key'], 'status': 'paused_capacity', 'error': str(exc)}
                        paused = True
                    except Exception as exc:
                        result = {'key': task['key'], 'status': 'failed', 'error': str(exc)}
                        state['failed'] += 1
                    state['last_results'] = (state['last_results'] + [result])[-12:]
                    print(json.dumps(result), flush=True)
                state['seconds'] = time.perf_counter() - began
                if paused:
                    state['status'] = 'paused_capacity'
                save(output / 'status.json', state)
                if paused or state['failed'] >= 20:
                    break
        if state['status'] != 'paused_capacity':
            state['status'] = 'complete' if state['completed'] == state['total'] else 'incomplete'
        save(output / 'status.json', state)
        print(json.dumps(state, indent=2))


if __name__ == '__main__':
    main()
