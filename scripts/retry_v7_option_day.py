"""Retry missing daily/minute option objects without resetting the acquisition quota."""
from pathlib import Path
import argparse
import fcntl
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from scripts.download_v7_data import acquire, tasks, save
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--date', required=True)
    ap.add_argument('--status', type=Path, required=True)
    args = ap.parse_args()
    calendar = json.loads((args.source / 'calendar.json').read_text())
    if args.date not in {s['date'] for s in calendar['sessions']}:
        raise ValueError('Requested date must be in the captured session calendar')
    results = []
    with (args.source.parent / '.acquisition.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for task in tasks([], calendar['sessions'], args.date, args.date, ['day_aggs', 'minute_aggs']):
            try:
                results.append(acquire(str(args.source), task, 100))
            except Exception as exc:
                results.append({'key': task['key'], 'status': 'failed', 'error': str(exc)})
            save(args.status, {'date': args.date, 'results': results, 'research_ready': False})
    print(json.dumps(results, indent=2))
    if any(r['status'] == 'failed' for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
