"""Capture Alpaca corporate actions, including spin-offs and reorganizations."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import gzip
import json
import sys
import time
import uuid
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import requests
    from scripts.download_v7_data import get_json, quota_update, tree_bytes, TASK_RESERVATION
    from nn_meta.v7.storage import identity, receipt, transaction, verify, sha
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--budget-root', type=Path, required=True)
    ap.add_argument('--start', required=True)
    ap.add_argument('--end', required=True)
    args = ap.parse_args()
    for day in (args.start, args.end):
        if datetime.strptime(day, '%Y-%m-%d').strftime('%Y-%m-%d') != day:
            raise ValueError('Explicit ISO process dates required')
    if args.start > args.end or not args.output.resolve().is_relative_to(args.budget_root.resolve()):
        raise ValueError('Chronological process-date scope and shared quota required')
    query = {'start': args.start, 'end': args.end, 'limit': 1000, 'sort': 'asc',
             'region': 'us', 'data_quality': 'all'}
    declaration = {'endpoint': 'https://data.alpaca.markets/v1/corporate-actions', 'params': query}
    fingerprint = identity(declaration)
    if args.output.exists():
        verify(args.output, expected_identity=fingerprint)
        return
    source_hash = sha(__file__)
    key = uuid.uuid4().hex
    quota_update(args.budget_root, reserve=key)
    used, counts = 0, {}
    try:
        with transaction(args.output) as temp, requests.Session() as session:
            params, seen = query.copy(), set()
            for page in range(2000):
                if sha(__file__) != source_hash:
                    raise ValueError('Capture source changed during the run')
                raw, body = get_json(session, declaration['endpoint'], params)
                groups = body.get('corporate_actions')
                if not isinstance(groups, dict) or not all(isinstance(v, list) for v in groups.values()):
                    raise ValueError('Malformed corporate action groups')
                for kind, values in groups.items():
                    if any(not isinstance(row, dict) for row in values):
                        raise ValueError('Malformed corporate action record')
                    counts[kind] = counts.get(kind, 0) + len(values)
                payload = gzip.compress(raw, mtime=0)
                if used + len(payload) > TASK_RESERVATION // 2:
                    raise ValueError('Corporate action capture exceeds reservation')
                (temp / f'page-{page:04d}.json.gz').write_bytes(payload)
                used += len(payload)
                print(json.dumps({'page': page, 'records': sum(counts.values())}), flush=True)
                token = body.get('next_page_token')
                if not token:
                    break
                if token in seen:
                    raise ValueError('Corporate action pagination loop')
                seen.add(token)
                params['page_token'] = token
                time.sleep(.4)
            else:
                raise ValueError('Corporate action page budget exhausted')
            receipt(temp, {'identity': fingerprint, 'query': declaration, 'counts': counts,
                'pages': page + 1, 'source_sha256': source_hash,
                'retrieved_at': datetime.now(timezone.utc).isoformat(),
                'historical_publication_vintage_verified': False,
                'purpose': 'event reconciliation only; process dates do not prove publication availability'})
            used = tree_bytes(temp)
    finally:
        if not args.output.exists():
            used = sum(tree_bytes(p) for p in args.output.parent.glob(args.output.name + '.partial-*'))
        quota_update(args.budget_root, finish=(key, used))


if __name__ == '__main__':
    main()
