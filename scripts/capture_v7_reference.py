"""Capture immutable historical ticker identity and event evidence within V7 quota."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import requests
    from dotenv import load_dotenv
    from nn_meta.v7.storage import transaction, receipt, identity, verify
    from scripts.download_v7_data import quota_update, tree_bytes, TASK_RESERVATION
    ap = argparse.ArgumentParser(description=__doc__)
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument('--symbols', type=Path)
    scope.add_argument('--dated-requests', type=Path,
                       help='JSON list of explicit ticker/date identity observations')
    scope.add_argument('--contract-requests', type=Path,
                       help='JSON list of explicit option contract/date metadata observations')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--budget-root', type=Path, required=True)
    ap.add_argument('--limit', type=int)
    args = ap.parse_args()
    if not args.output.resolve().is_relative_to(args.budget_root.resolve()):
        raise ValueError('Reference captures must share the download quota root')
    load_dotenv(ROOT/'.env')
    session = requests.Session()
    dated = None
    if args.dated_requests or args.contract_requests:
        dated = json.loads((args.dated_requests or args.contract_requests).read_text())
        if not isinstance(dated, list) or len(dated) > 10000:
            raise ValueError('Bounded dated request list required')
        import re
        if args.contract_requests:
            from options.data.provider import parse_occ_symbol
            converted = []
            for row in dated:
                if set(row) != {'contract', 'date'}:
                    raise ValueError('Explicit contract/date scope required')
                parse_occ_symbol(row['contract'])
                converted.append({'symbol': row['contract'].removeprefix('O:'), 'date': row['date']})
            dated = converted
        for row in dated:
            if (set(row) != {'symbol', 'date'} or not re.fullmatch(r'[A-Z][A-Z0-9.]*w?', row['symbol'])
                    or datetime.strptime(row['date'], '%Y-%m-%d').strftime('%Y-%m-%d') != row['date']):
                raise ValueError('Invalid dated reference request')
    symbols = sorted(set(r['symbol'] for r in dated)) if dated is not None else sorted(set(args.symbols.read_text().split()))
    if args.limit: symbols = symbols[:args.limit]
    for symbol in symbols:
        queries = [('events', f'/vX/reference/tickers/{symbol}/events', {'types':'ticker_change'})]
        queries += [(day, f'/v3/reference/tickers/{symbol}', {'date':day})
                    for day in ['2022-03-07', '2023-01-03', '2024-01-02', '2025-01-02', '2026-09-14']]
        if dated is not None:
            queries = [(day, f'/v3/reference/tickers/{symbol}', {'date': day})
                       for day in sorted({r['date'] for r in dated if r['symbol'] == symbol})]
            if args.contract_requests:
                queries = [(day, f'/v3/reference/options/contracts/O:{symbol}', {'as_of': day})
                           for day, _, _ in queries]
        for name, path, params in queries:
            query = {'path':path,'params':params}; fingerprint=identity(query)
            destination=args.output/symbol/name
            if destination.exists():
                verify(destination,expected_identity=fingerprint);continue
            key=uuid.uuid4().hex;quota_update(args.budget_root,reserve=key);used=0
            try:
                for attempt in range(5):
                    try:
                        r=session.get('https://api.massive.com'+path,params=params,
                                      headers={'Authorization':'Bearer '+os.environ['MASSIVE_API_KEY']},
                                      timeout=30,allow_redirects=False)
                    except requests.RequestException:
                        raise RuntimeError('Reference transport failed') from None
                    if r.status_code not in (429,500,502,503,504):break
                    time.sleep(2**attempt)
                if len(r.content)>TASK_RESERVATION//2:raise ValueError('Oversized reference response')
                if r.status_code not in (200,404):
                    raise RuntimeError(f'Reference HTTP {r.status_code}: {symbol}/{name}')
                body=r.json()
                if body.get('next_url'):raise ValueError('Unexpected unconsumed reference pagination')
                with transaction(destination) as temp:
                    (temp/'response.json').write_bytes(r.content)
                    receipt(temp,{'identity':fingerprint,'query':query,'http_status':r.status_code,
                                  'retrieved_at':datetime.now(timezone.utc).isoformat(),
                                  'historical_publication_vintage_verified':False})
                    used=tree_bytes(temp)
                print(json.dumps({'symbol':symbol,'query':name,'http_status':r.status_code}),flush=True)
            finally:
                if not destination.exists():
                    used=sum(tree_bytes(p) for p in destination.parent.glob(destination.name+'.partial-*'))
                quota_update(args.budget_root,finish=(key,used))


if __name__=='__main__':main()
