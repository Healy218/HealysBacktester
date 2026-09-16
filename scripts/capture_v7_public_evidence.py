"""Capture bounded public primary-source documents with immutable V7 receipts."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import json
import re
import sys
import uuid
from urllib.parse import urlsplit
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import requests
    from nn_meta.v7.storage import identity, verify, transaction, receipt
    from scripts.download_v7_data import quota_update, tree_bytes, disk_guard
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('requests', 'output', 'budget-root'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    queries = json.loads(args.requests.read_text())
    if not isinstance(queries, list) or not 0 < len(queries) <= 1000:
        raise ValueError('A bounded nonempty public-document list is required')
    if not args.output.resolve().is_relative_to(args.budget_root.resolve()):
        raise ValueError('Public evidence must share the acquisition cap')
    ids = []
    for item in queries:
        parsed = urlsplit(item['url'])
        if (set(item) != {'evidence_id','url'} or not re.fullmatch(r'[a-z0-9-]+',item['evidence_id'])
                or parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password):
            raise ValueError('Named HTTPS public evidence only')
        ids.append(item['evidence_id'])
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate evidence IDs')
    failed = []
    with requests.Session() as session:
        session.headers['User-Agent'] = 'HealysBacktester research evidence archive'
        for item in queries:
            path = args.output/item['evidence_id']
            if path.exists():
                verify(path, expected_identity=identity(item))
                continue
            disk_guard(args.budget_root,100)
            key=uuid.uuid4().hex
            quota_update(args.budget_root,reserve=key)
            before=sum(tree_bytes(p) for p in path.parent.glob(path.name+'.partial-*'))
            used=0
            try:
                with transaction(path) as temp:
                    with session.get(item['url'],timeout=30,stream=True,allow_redirects=True) as response:
                        if response.status_code != 200:
                            raise ValueError('Public evidence HTTP '+str(response.status_code))
                        if urlsplit(response.url).scheme != 'https':
                            raise ValueError('Public evidence redirected outside HTTPS')
                        content_type=response.headers.get('Content-Type','')
                        with (temp/'response.bin').open('wb') as out:
                            for block in response.iter_content(65536):
                                used+=len(block)
                                if used>50*1024**2:
                                    raise ValueError('Public document exceeds 50 MiB bound')
                                out.write(block)
                        receipt(temp,{'identity':identity(item),'query':item,'final_url':response.url,
                            'content_type':content_type,'retrieved_at':datetime.now(timezone.utc).isoformat(),
                            'historical_availability':'must be established from document content',
                            'research_ready':False})
                print(json.dumps({'evidence_id':item['evidence_id'],'bytes':used,'status':'captured'}),flush=True)
            except (requests.RequestException,ValueError) as exc:
                failed.append(item['evidence_id'])
                # Never echo response/request objects which may contain headers.
                print(json.dumps({'evidence_id':item['evidence_id'],'status':'failed','error_type':type(exc).__name__,
                    'reason':str(exc) if isinstance(exc,ValueError) else 'public-document transport failed'}),flush=True)
            finally:
                used=(tree_bytes(path) if path.exists() else 0) + sum(
                    tree_bytes(p) for p in path.parent.glob(path.name+'.partial-*'))
                quota_update(args.budget_root,finish=(key,max(0,used-before)))
    return int(bool(failed))


if __name__=='__main__':raise SystemExit(main())
