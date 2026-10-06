"""Compute full-calendar ETFE context requests and packed signal memberships."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nn_meta.etfe import window_demand as w
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','context','signals']);p.add_argument('--root',type=Path,required=True);p.add_argument('--max-families',type=int);a=p.parse_args();root=a.root.resolve()
    if root.parent!=ROOT/'nn_meta/validation' or not root.name.startswith('etfe-window-demand-'):p.error('Isolated ETFE root required')
    result=w.prepare(root) if a.command=='prepare' else w.context(root) if a.command=='context' else w.signals(root,max_families=a.max_families)
    print(json.dumps({k:v for k,v in result.items() if k not in ('sources','inputs')},indent=2))
