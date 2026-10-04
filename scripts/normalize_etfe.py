"""Prepare or run bounded typed normalization of fresh Alpaca ETFE inputs."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe.normalization import normalize,prepare_normalization


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','run'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--input',type=Path,action='append',default=[])
    p.add_argument('--calendar',type=Path)
    p.add_argument('--max-partitions',type=int)
    a=p.parse_args();root=a.root.resolve()
    if root.parent!=ROOT/'nn_meta/data_cache_etfe' or not root.name.startswith('normalized-'):
        p.error('Direct ETFE normalized-* root required')
    if a.command=='prepare':
        if not a.input or a.calendar is None:p.error('--input and --calendar required')
        r=prepare_normalization(root,a.input,a.calendar);print(json.dumps(dict(plan_sha256=r['sha256'],inputs=len(a.input))))
    else:
        r=normalize(root,max_partitions=a.max_partitions)
        print(json.dumps({k:v for k,v in r.items() if k!='partition_receipts'},indent=2))
        if not r['normalized_complete']:raise SystemExit(2)


if __name__=='__main__':main()
