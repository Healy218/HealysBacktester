"""Retain a returned web-tool extraction, explicitly distinct from raw HTTP bytes.

The input is the unedited tool response, including its source URL and extraction
metadata. This records provenance, not independent proof of a historical posting.
"""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import json
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.storage import identity, transaction, receipt, verify
    from scripts.download_v7_data import quota_update, tree_bytes, disk_guard
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--url',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--budget-root',type=Path,required=True)
    args=p.parse_args();body=args.input.read_bytes()
    if (not args.url.startswith('https://') or args.url not in body.decode('utf-8')
            or not body or len(body)>5*1024**2
            or not args.output.resolve().is_relative_to(args.budget_root.resolve())):
        raise ValueError('Bounded source-attributed web-tool text required')
    query=dict(url=args.url, capture_method='web_tool_text_extraction',
        original_response_identity=identity(body.decode('utf-8')))
    if args.output.exists():verify(args.output,expected_identity=identity(query));return
    disk_guard(args.budget_root,100);key=uuid.uuid4().hex
    quota_update(args.budget_root,reserve=key)
    try:
        with transaction(args.output) as temp:
            (temp/'response.bin').write_bytes(body)
            receipt(temp,dict(identity=identity(query),query=query,final_url=args.url,
                content_type='text/plain; charset=utf-8',capture_method=query['capture_method'],
                raw_origin_http_bytes=False,retrieved_at=datetime.now(timezone.utc).isoformat(),
                historical_availability='not established by current extraction',research_ready=False))
    finally:
        quota_update(args.budget_root,finish=(key,tree_bytes(args.output) if args.output.exists() else 0))
    print(json.dumps(dict(output=str(args.output),bytes=len(body),capture_method=query['capture_method'])))


if __name__=='__main__':main()
