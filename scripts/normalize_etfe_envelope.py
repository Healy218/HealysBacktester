"""Normalize or audit an ETFE envelope capture (option minute bars or SIP stock quotes)."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import envelope_normalize as n


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['run','audit']);parser.add_argument('kind',choices=['bars','quotes'])
    parser.add_argument('--raw',type=Path,required=True);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve()
    if root.parent!=ROOT/'nn_meta/data_cache_etfe' or not root.name.startswith('normalized-'):
        parser.error('Direct ETFE normalized-* root required')
    f=n.normalize if args.command=='run' else n.audit
    print(json.dumps(f(args.kind,args.raw.resolve(),root),indent=2))
