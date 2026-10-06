"""Independently recompute ETFE closing-auction exercise references from raw capture pages."""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import stock_trade_capture as t

VENUES={'SPY':('P',),'VOO':('P',),'QQQ':('Q','T')}


def recompute(root):
    out={}
    for item in t.load_plan(root)['jobs']:
        sym=item['params']['symbols'];pages=t.committed(root,item)[0]
        df=pd.DataFrame([r for _,body,_ in pages for r in (body['trades'] or {}).get(sym,[])])
        key=(sym,item['params']['start'])
        if df.empty:out[key]=None;continue
        lst=df[df.x.isin(VENUES[sym])]
        m=lst[lst.c.map(lambda c:'M' in c)].p.unique();six=lst[lst.c.map(lambda c:'6' in c)].p.unique()
        if len(m)==1 and (len(six)==0 or m[0] in six):out[key]=float(m[0])
        elif len(m)==0 and len(six)==1:out[key]=float(six[0])
        else:out[key]=None
    return out


def audit(root):
    root=Path(root);summary=json.loads((root/'SUMMARY.json').read_text())
    if t.sha((root/'REFERENCES.parquet').read_bytes())!=summary['references_sha256']:raise ValueError('References hash')
    ref=pq.read_table(root/'REFERENCES.parquet').to_pandas();expected={}
    for path,digest in summary['capture_plans'].items():
        if t.load_plan(ROOT/path)['sha256']!=digest:raise ValueError('Capture plan drift')
        expected.update(recompute(ROOT/path))
    starts=[(pd.Timestamp(c)-pd.Timedelta(seconds=5)).isoformat() for c in ref.close_utc]
    got=[None if pd.isna(v) else float(v) for v in ref.reference]
    want=[expected[(s,st)] for s,st in zip(ref.symbol,starts)]
    if len(expected)!=len(ref) or got!=want:raise ValueError('Reference recomputation mismatch')
    result=dict(schema='etfe-exercise-references-independent-audit-v1',sessions=len(ref),
        resolved=sum(v is not None for v in got),recomputation_matches=True,
        summary_sha256=t.sha((root/'SUMMARY.json').read_bytes()),auditor_sha256=t.sha(Path(__file__).read_bytes()))
    t.save(root/'INDEPENDENT_AUDIT.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(audit(args.root.resolve()),indent=2))
