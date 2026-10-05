"""Prepare, stream or verify an isolated ETFE joined-diagnostic study."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nn_meta.etfe.joined_pilot import prepare,verify,run

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','run','verify'])
    p.add_argument('--root',required=True,type=Path);p.add_argument('--max-chunks',type=int)
    a=p.parse_args();root=a.root.resolve()
    if root.parent!=ROOT/'nn_meta/validation' or not root.name.startswith('etfe-joined-'):p.error('Isolated ETFE joined root required')
    if a.max_chunks is not None and a.max_chunks<1:p.error('Positive chunk limit required')
    if a.command=='run':
        r=run(root,a.max_chunks);print(json.dumps(r,indent=2))
        if not r['complete']:raise SystemExit(2)
    else:
        r=prepare(root) if a.command=='prepare' else verify(root)
        print(json.dumps(dict(plan_sha256=r['sha256'],chunks=len(r['chunks']),fields=len(r['feature_schema']['fields']))))
