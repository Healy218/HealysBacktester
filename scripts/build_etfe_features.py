"""Build ETFE features v1 (221 values + 221 masks) for one ticker's decision-clock rows."""
import argparse
import json
import resource
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import feature_build as f
from nn_meta.etfe.causal_pilot import SETUP


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ticker',choices=['SPY','QQQ']);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve()
    if root.parent!=ROOT/'nn_meta/validation' or not root.name.startswith('etfe-features-'):
        parser.error('Direct nn_meta/validation/etfe-features-* root required')
    root.mkdir(exist_ok=True)
    if (root/f'{args.ticker}.json').exists():parser.error('Ticker already built in this root; use a successor root')
    census=f.census_daily();context=f.daily_context(args.ticker,census);bars,windows=f.load_bars(args.ticker)
    catalog=json.loads((SETUP/'catalog.json').read_text())['records'];result={}
    for minutes in (15,5,1):
        r=f.build_scope(args.ticker,minutes,root,context,bars,windows,[c for c in catalog if c['signal_minutes']==minutes])
        result[r['scope']]=r;print(json.dumps({k:v for k,v in r.items() if k!='fill_by_field'}),flush=True)
    result['peak_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    (root/f'{args.ticker}.json').write_text(json.dumps(result,indent=2)+'\n')
