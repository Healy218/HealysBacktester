"""Apply ETFE-0 dated-input policy v1 to fresh census, calendar, action and option inputs."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import dated_policy as d


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve()
    if root.parent!=ROOT/'nn_meta/validation' or not root.name.startswith('etfe-dated-policy-'):
        parser.error('Direct nn_meta/validation/etfe-dated-policy-* root required')
    print(json.dumps(d.build(root),indent=2))
