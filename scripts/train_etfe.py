"""Run declared ETFE experiment-v2 fits (resumable: completed receipts are skipped).

Fits are grouped by fold; each fold's matrix is loaded once (never the whole dataset) and released
before the next fold. Run under a hard memory cap, e.g.
  systemd-run --user --scope -p MemoryMax=20G ./venv/bin/python scripts/train_etfe.py --root ...
"""
import argparse
import gc
import json
import resource
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import train as t


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--fit',action='append',help='fit id; default all 84')
    parser.add_argument('--worker',type=int,default=0);parser.add_argument('--workers',type=int,default=1)
    args=parser.parse_args();root=args.root.resolve()
    if root.parent!=ROOT/'nn_meta/validation' or not root.name.startswith('etfe-training-'):
        parser.error('Direct nn_meta/validation/etfe-training-* root required')
    root.mkdir(exist_ok=True);e,m=t.load_experiment()
    fits=args.fit or e['fit_ids'];fits=[f for i,f in enumerate(fits) if i%args.workers==args.worker]
    by_fold=defaultdict(list)
    for f in fits:by_fold[f.split('/')[0]].append(f)
    for fold,ids in by_fold.items():
        pending=[f for f in ids if not (root/'receipts'/(f.replace('/','__')+'.json')).exists()]
        if not pending:print(json.dumps(dict(fold=fold,skipped=len(ids))),flush=True);continue
        started=time.monotonic();data,Z,width=t.load_fold(e,m,fold)
        print(json.dumps(dict(fold=fold,rows=len(data),matrix_gib=round(Z.nbytes/2**30,2),load_seconds=round(time.monotonic()-started,1),
            peak_rss_gib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/2**20,2))),flush=True)
        for fit_id in ids:
            r,skipped=t.run_fit(root,fit_id,e,m,data,Z,width)
            print(json.dumps(dict(fit=fit_id,skipped=skipped,train_rows=r['train_rows'],evaluate_rows=r['evaluate_rows'],
                seconds=round(r['elapsed_seconds'],1),peak_rss_gib=round(r['peak_rss_bytes']/2**30,2))),flush=True)
        t.MEDIANS.pop(fold,None);del data,Z;gc.collect()
