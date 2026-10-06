"""Factor full ETFE diagnostic signals into exact bar/trade acquisition windows."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nn_meta.etfe import exact_windows as e
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run']);p.add_argument('--root',type=Path,required=True);p.add_argument('--source',type=Path);a=p.parse_args();root=a.root.resolve()
    if root.parent!=ROOT/'nn_meta/validation' or not root.name.startswith('etfe-exact-windows-'):p.error('Isolated ETFE root required')
    r=e.prepare(root,a.source) if a.command=='prepare' else e.run(root);print(json.dumps({k:v for k,v in r.items() if k not in ('sources','inputs')},indent=2))
