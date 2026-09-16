"""Bounded original news captures for dated action/halt evidence, not features."""
from pathlib import Path
import argparse
from datetime import date, datetime, timezone, timedelta
import gzip
import json
import re
import sys
import time
import uuid
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def capture(args):
    import requests
    from nn_meta.v7.storage import identity, sha, verify, transaction, receipt
    from scripts.download_v7_data import get_json, quota_update, tree_bytes, disk_guard
    symbols = args.symbols.split(',')
    if (not 0 < len(symbols) <= 50 or len(set(symbols)) != len(symbols)
            or any(not re.fullmatch(r'[A-Z][A-Z0-9.]{0,14}', s) for s in symbols)
            or not 0 < (date.fromisoformat(args.end)-date.fromisoformat(args.start)).days <= 31
            or not args.output.resolve().is_relative_to(args.budget_root.resolve())):
        raise ValueError('Explicit symbols, bounded half-open date range and shared quota required')
    query = dict(path='/v1beta1/news', params=dict(symbols=','.join(sorted(symbols)),
                 start=args.start+'T00:00:00Z',
                 end=(date.fromisoformat(args.end)-timedelta(days=1)).isoformat()+'T23:59:59.999999999Z', sort='asc',
                 limit=50, include_content=True, exclude_contentless=False))
    if args.output.exists():
        verify(args.output, expected_identity=identity(query))
        return dict(output=str(args.output), status='reused')
    source = sha(__file__)
    disk_guard(args.budget_root, 100)
    reservation = uuid.uuid4().hex
    quota_update(args.budget_root, reserve=reservation)
    before = sum(tree_bytes(p) for p in args.output.parent.glob(args.output.name+'.partial-*'))
    try:
        with transaction(args.output) as temp, requests.Session() as session:
            params, seen, ids, total = dict(query['params']), set(), set(), 0
            for page in range(100):
                time.sleep(.5)
                raw, body = get_json(session, 'https://data.alpaca.markets'+query['path'], params)
                rows = body.get('news')
                if not isinstance(rows, list) or any(not isinstance(r, dict) or not r.get('id') for r in rows):
                    raise ValueError('Invalid news page')
                for row in rows:
                    if row['id'] in ids:
                        raise ValueError('Duplicate news ID during pagination')
                    ids.add(row['id'])
                compressed = gzip.compress(raw, mtime=0)
                total += len(compressed)
                if total > 50*1024**2:
                    raise ValueError('News capture exceeds 50 MiB bound')
                disk_guard(args.budget_root, 100)
                (temp/f'page-{page:04d}.json.gz').write_bytes(compressed)
                token = body.get('next_page_token')
                if not token:
                    break
                if token in seen:
                    raise ValueError('Repeated news pagination token')
                seen.add(token); params['page_token'] = token
            else:
                raise ValueError('News pagination bound exceeded')
            if sha(__file__) != source:
                raise ValueError('News capture source changed')
            receipt(temp, dict(identity=identity(query), query=query, articles=len(ids),
                source_sha256=source, retrieved_at=datetime.now(timezone.utc).isoformat(),
                research_ready=False, purpose='Review original publication and update clocks; not automatic action admission'))
        return dict(articles=len(ids), output=str(args.output), research_ready=False, status='captured')
    finally:
        used = (tree_bytes(args.output) if args.output.exists() else 0) + sum(
            tree_bytes(p) for p in args.output.parent.glob(args.output.name+'.partial-*'))
        quota_update(args.budget_root, finish=(reservation, max(0, used-before)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('symbols', 'start', 'end'):
        parser.add_argument('--'+key, required=True)
    for key in ('output', 'budget-root'):
        parser.add_argument('--'+key, type=Path, required=True)
    print(json.dumps(capture(parser.parse_args())))


if __name__ == '__main__': main()
