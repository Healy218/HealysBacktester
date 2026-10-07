"""Run ETFE candidate selection v2 over the full signal census."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import selection_v2 as s


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve()
    if root.parent!=ROOT/'nn_meta/validation' or not root.name.startswith('etfe-selection-v2-'):
        parser.error('Direct nn_meta/validation/etfe-selection-v2-* root required')
    r=s.run(root);print(json.dumps({k:v for k,v in r.items() if k!='scopes'},indent=2,default=str))
