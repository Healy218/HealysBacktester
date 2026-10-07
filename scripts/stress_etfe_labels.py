"""Run the 27 declared ETFE execution stress profiles through the label kernel for one ticker."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import label_build as b


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ticker',choices=['SPY','QQQ','VOO']);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--profile',action='append')
    args=parser.parse_args();root=args.root.resolve()
    if root.parent!=ROOT/'nn_meta/validation' or not root.name.startswith('etfe-label-stress-'):
        parser.error('Direct nn_meta/validation/etfe-label-stress-* root required')
    root.mkdir(exist_ok=True)
    if (root/f'{args.ticker}.json').exists():parser.error('Ticker already stressed in this root; use a successor root')
    r=b.run_stress(args.ticker,root,args.profile);(root/f'{args.ticker}.json').write_text(json.dumps(r,indent=2,default=str)+'\n')
