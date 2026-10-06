"""Prepare or construct the complete range census and dated-terms rejection audit."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import full_coverage as c

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','run'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--raw',type=Path)
    p.add_argument('--frontier',type=Path)
    args=p.parse_args();root=args.root.resolve()
    if root.parent!=ROOT/'nn_meta/validation' or not root.name.startswith('etfe-full-coverage-'):
        p.error('Isolated full coverage validation root required')
    if args.command=='prepare':
        if args.raw is None or args.frontier is None:p.error('--raw and --frontier required')
        r=c.prepare(root,args.raw,args.frontier); print(json.dumps(dict(sha256=r['sha256'])))
    else:
        r=c.run(root);print(json.dumps(dict(summary=r['summary'],dated_reason_counts=r['dated_reason_counts'])))
