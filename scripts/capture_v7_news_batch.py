"""Capture predeclared action-publication windows with at most four workers."""
from pathlib import Path
import argparse
import fcntl
import json
import re
import sys
from types import SimpleNamespace
import uuid
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def work(payload):
    from scripts.capture_v7_news import capture
    return capture(SimpleNamespace(**payload))


def main():
    from nn_meta.v7.runtime import worker_pool
    from nn_meta.v7.storage import sha
    from scripts.download_v7_data import save, quota_update
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('requests', 'output', 'budget-root'):
        parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--workers', type=int, required=True)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4 or not args.output.resolve().is_relative_to(args.budget_root.resolve()):
        raise ValueError('One to four workers and shared acquisition root required')
    requests = json.loads(args.requests.read_text())
    if requests.get('schema') != 'v7-action-news-requests-v1' or not requests.get('queries'):
        raise ValueError('Explicit news request manifest required')
    queries = requests['queries']
    if (len(queries) > 2000 or any(set(q) != {'id', 'symbols', 'start', 'end'}
            or not re.fullmatch(r'[a-z0-9-]+', q['id']) or not isinstance(q['symbols'], list) for q in queries)
            or len({q['id'] for q in queries}) != len(queries)):
        raise ValueError('Distinct bounded news queries required')
    sources = {str(p): sha(p) for p in (Path(__file__), ROOT/'scripts/capture_v7_news.py',
                                       ROOT/'scripts/download_v7_data.py', args.requests)}
    manifest = dict(sources=sources, requests=requests, research_ready=False)
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.budget_root/'.acquisition.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = args.output/'acquisition.json'
        if path.exists() and json.loads(path.read_text()) != manifest:
            raise ValueError('News batch scope/source changed; use a fresh directory')
        reservation = uuid.uuid4().hex
        quota_update(args.budget_root, reserve=reservation)
        metadata = [path, args.output/'status.json']
        before = sum(p.stat().st_size for p in metadata if p.exists())
        try:
            save(path, manifest)
            queries = requests['queries']
            status = dict(total=len(queries), completed=0, failed=0, research_ready=False)
            with worker_pool(args.workers, threads=1) as pool:
                for offset in range(0, len(queries), args.workers):
                    if any(sha(p) != digest for p, digest in sources.items()):
                        raise ValueError('News batch source changed')
                    futures = []
                    for query in queries[offset:offset+args.workers]:
                        payload = dict(symbols=','.join(query['symbols']), start=query['start'], end=query['end'],
                            output=args.output/query['id'], budget_root=args.budget_root)
                        futures.append((query['id'], pool.submit(work, payload)))
                    results = []
                    for name, future in futures:
                        try:
                            result = future.result(); status['completed'] += 1
                            results.append(dict(query=name, **result))
                        except Exception as exc:
                            status['failed'] += 1
                            results.append(dict(query=name, error=str(exc)))
                    status['last_results'] = results
                    save(args.output/'status.json', status)
                    print(json.dumps(status), flush=True)
                    if status['failed']:
                        raise RuntimeError('News batch incomplete; explicit failure retained')
        finally:
            after = sum(p.stat().st_size for p in metadata if p.exists())
            quota_update(args.budget_root, finish=(reservation, max(0, after-before)))


if __name__ == '__main__': main()
