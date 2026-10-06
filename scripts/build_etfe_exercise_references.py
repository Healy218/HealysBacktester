"""Extract ETFE closing-auction exercise references, pin statistics and a minute-bar sanity check."""
import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import closing_reference as c, exercise_reference as x, stock_trade_capture as t

YEARS=(2024,2025,2026)


def capture_root(year):
    return ROOT/f'nn_meta/data_cache_etfe/alpaca-fresh-closing-auction-{year}-20261006-r0'


def last_regular_bar_close():
    """Close of the final regular-session SIP minute bar per (symbol, session)."""
    root=ROOT/'nn_meta/data_cache_etfe/normalized-20261004-main-r0';out={}
    closes=c.sessions()
    for meta_path in (root/'partitions').glob('*.json'):
        meta=json.loads(meta_path.read_text())
        if meta['route']!='stock_bars' or not meta['rows']:continue
        b=pq.read_table(root/meta['data'],columns=['symbol','timestamp_ns','session_date','close']).to_pandas()
        for (sym,day),g in b.groupby(['symbol','session_date']):
            if day not in closes:continue
            last=g[g.timestamp_ns<=closes[day].value-60_000_000_000]
            if len(last):out[sym,day]=float(last.loc[last.timestamp_ns.idxmax(),'close'])
    return out


def build(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    closes=c.sessions();by_close={v:k for k,v in closes.items()};rows=[];plans={}
    for y in YEARS:
        root=capture_root(y);plan=t.load_plan(root);plans[str(root.relative_to(ROOT))]=plan['sha256']
        for item in plan['jobs']:
            hist,_,done=t.committed(root,item)
            if not done:raise ValueError(f'Incomplete capture job {item["id"]}')
            trades=[r for _,b,_ in hist for _,r in t.rows(b,item)]
            sym=item['params']['symbols'];close=pd.Timestamp(item['params']['start'])+c.BEFORE
            ref=x.official_close(sym,trades)
            rows.append(dict(symbol=sym,session_date=by_close[close],close_utc=close.isoformat(),
                status=ref['status'],reason=ref['reason'],reference=ref['price'],trades=len(trades),
                job_id=item['id'],body_sha256=[h[0]['body_sha256'] for h in hist]))
    pq.write_table(pa.Table.from_pylist(rows),out/'REFERENCES.parquet')
    ref={(r['symbol'],r['session_date']):r['reference'] for r in rows if r['status']=='resolved'}
    # Pin statistics over admitted contracts expiring on resolved sessions.
    contracts=pq.read_table(c.POLICY/'CONTRACTS.parquet',columns=['underlying','expiration_date','right','strike','status']).to_pandas()
    contracts=contracts[contracts.status=='admitted']
    pins=Counter();evaluated=0;exercised=0
    for u,e,r,k in zip(contracts.underlying,contracts.expiration_date,contracts.right,contracts.strike):
        if (u,e) not in ref:continue
        o=c.exercise_outcome(r,k,ref[u,e]);evaluated+=1;exercised+=o['exercised'];pins[u]+=o['pin']
    bars=last_regular_bar_close();diffs=[]
    for (u,e),p in ref.items():
        if (u,e) in bars:diffs.append(abs(p-bars[u,e])/p)
    d=pd.Series(diffs)
    summary=dict(schema='etfe-exercise-references-v1',spec='docs/specs/ETFE_CLOSING_AUCTION_20261006.md',
        sessions=len(rows),status=dict(Counter(r['status'] for r in rows)),reasons=dict(Counter(r['reason'] for r in rows)),
        unresolved=[[r['symbol'],r['session_date'].isoformat(),r['reason']] for r in rows if r['status']!='resolved'],
        contracts_evaluated=evaluated,contracts_exercised=exercised,pins_within_5c=dict(pins),
        bar_sanity=dict(sessions_compared=len(d),median_rel_diff=float(d.median()) if len(d) else None,
            p99_rel_diff=float(d.quantile(.99)) if len(d) else None,max_rel_diff=float(d.max()) if len(d) else None,
            note='final regular SIP minute-bar close vs official close; diagnostic only'),
        capture_plans=plans,references_sha256=t.sha((out/'REFERENCES.parquet').read_bytes()),
        ready_for_build=False,ready_for_training=False)
    t.save(out/'SUMMARY.json',summary)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve()
    if root.parent!=ROOT/'nn_meta/validation' or not root.name.startswith('etfe-exercise-references-'):
        parser.error('Direct nn_meta/validation/etfe-exercise-references-* root required')
    print(json.dumps(build(root),indent=2,default=str))
