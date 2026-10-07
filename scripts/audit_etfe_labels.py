"""Independently check ETFE kernel-v1 labels against normalized envelope bars and census counts.

For every filled row (settled, censored, funding or input after a fill): the entry bar starts at the
signal (next_bar_vwap) or one minute before it (signal_bar_vwap, labels r0-r2), its VWAP equals the recorded entry VWAP, quantity
respects floor(1% volume) and the $10,000 budget at unit = 100 x VWAP x 1.0015, and the debit
equals the half-even cents of gross + 0.1% fee + 0.05% slippage, summed in the
reference ledger's order. Row counts reconcile with selection v2.
"""
import argparse
from collections import Counter
from decimal import Decimal,ROUND_HALF_EVEN
import json
import math
import sys
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
BARS=ROOT/'nn_meta/data_cache_etfe/normalized-20261006-envelope-bars-r0'
SELECTION=ROOT/'nn_meta/validation/etfe-selection-v2-20261006-r0'


def cents(x):
    return int(Decimal(str(x)).quantize(Decimal('.01'),rounding=ROUND_HALF_EVEN)*100)


def bar_index(symbols):
    index={};seal=json.loads((BARS/'NORMALIZED.json').read_text())
    for key in seal['partition_receipts']:
        meta=json.loads((BARS/'partitions'/(key+'.json')).read_text())
        t=pq.read_table(BARS/meta['data'],columns=['symbol','timestamp_ns','vwap','volume'])
        t=t.filter(pc.is_in(t['symbol'],value_set=symbols))
        for s,ts,vw,v in zip(*(t[c].to_pylist() for c in ('symbol','timestamp_ns','vwap','volume'))):index[s,ts]=(vw,v)
    return index


def audit(root,fill_rule='next_bar_vwap'):
    root=Path(root);census=Counter();checked=0;problems=[]
    offset=0 if fill_rule=='next_bar_vwap' else 60_000_000_000  # entry bar start relative to the signal
    for path in sorted(root.glob('*-*.parquet')):
        t=pq.read_table(path).to_pandas();census.update(t.status)
        sel=pq.read_table(SELECTION/path.name,columns=['candidate']).to_pandas()
        if len(t)!=(sel.candidate!='').sum():problems.append(f'{path.stem}: row count {len(t)} != selection')
        filled=t[t.quantity>0].drop_duplicates(['contract','signal_at_ns'])
        import pyarrow as pa
        idx=bar_index(pa.array(sorted(filled.contract.unique()),pa.string()))
        for r in filled.itertuples(index=False):
            bar=idx.get((r.contract,r.signal_at_ns-offset))
            if bar is None or bar[0]!=r.entry_vwap:problems.append(f'{path.stem} {r.contract} {r.signal_at_ns}: entry bar');continue
            unit=100*bar[0]*1.0015
            if r.quantity>math.floor(.01*bar[1]) or r.quantity>math.floor(10000/unit) or cents(r.quantity*100*bar[0]+r.quantity*100*bar[0]*.001+r.quantity*100*bar[0]*.0005)!=r.debit_cents:
                problems.append(f'{path.stem} {r.contract} {r.signal_at_ns}: size/debit')
            checked+=1
        if len(problems)>50:break
    result=dict(schema='etfe-labels-independent-audit',fill_rule=fill_rule,rows=sum(census.values()),census=dict(census),
        unique_entries_checked=checked,problems=problems[:50],passed=not problems)
    (root/'INDEPENDENT_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--fill-rule',choices=['next_bar_vwap','signal_bar_vwap'],default='next_bar_vwap')
    args=parser.parse_args();print(json.dumps(audit(args.root.resolve(),args.fill_rule),indent=2))
