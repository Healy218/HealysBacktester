"""Build ETFE isolated-path labels (kernel v1) for one ticker's selection-v2 decision clocks."""
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
    parser.add_argument('--no-stop',action='store_true',help='v4: no premium stop (stop_fraction=None)')
    parser.add_argument('--intrinsic',action='store_true',help='close unsellable unfunded ITM expiries at intrinsic value')
    args=parser.parse_args();root=args.root.resolve()
    if root.parent!=ROOT/'nn_meta/validation' or not root.name.startswith('etfe-labels-'):
        parser.error('Direct nn_meta/validation/etfe-labels-* root required')
    root.mkdir(exist_ok=True)
    if any(root.glob(f'{args.ticker}-*.parquet')):parser.error('Ticker already built in this root; use a successor root')
    policy={**(dict(stop_fraction=None) if args.no_stop else {}),**(dict(unfunded_itm='intrinsic') if args.intrinsic else {})}
    r=b.run_ticker(args.ticker,root,policy or None);(root/f'{args.ticker}.json').write_text(json.dumps(r,indent=2,default=str)+'\n')
    print(json.dumps(dict(ticker=r['ticker'],elapsed_seconds=r['elapsed_seconds'])))
