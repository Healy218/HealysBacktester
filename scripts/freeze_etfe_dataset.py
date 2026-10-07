"""Freeze or verify the ETFE v1 dataset (joined audited features and labels)."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import dataset_freeze as d


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['freeze','verify']);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--labels',type=Path,default=d.LABELS)
    args=parser.parse_args();root=args.root.resolve()
    if root.parent!=ROOT/'nn_meta/validation' or not root.name.startswith('etfe-dataset-'):
        parser.error('Direct nn_meta/validation/etfe-dataset-* root required')
    print(json.dumps(d.freeze(root,args.labels.resolve()) if args.command=='freeze' else d.verify(root),indent=2,default=str))
