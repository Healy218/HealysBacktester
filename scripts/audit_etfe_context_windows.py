"""Independently reconcile every full-context request membership and UTC bound."""
from collections import defaultdict,Counter
from datetime import date,timedelta
import argparse,json,sys
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nn_meta.etfe import acquisition as a,window_demand as w
from nn_meta.etfe.expansion import read_calendar


def audit(root):
    root=Path(root);p=w.load(root);seal=json.loads((root/'CONTEXT.json').read_text())
    if a.sha((root/seal['path']).read_bytes())!=seal['sha256']:raise ValueError('Context data drift')
    by_expiry=defaultdict(set)
    census=json.loads((w.CENSUS/'CENSUS.json').read_text())
    for key,h in census['page_receipts'].items():
        mp=w.CENSUS/'partitions'/(key+'.json')
        if a.sha(mp.read_bytes())!=h:raise ValueError('Census receipt drift')
        meta=json.loads(mp.read_text());path=w.CENSUS/meta['data']
        if a.sha(path.read_bytes())!=meta['data_sha256']:raise ValueError('Contract drift')
        for raw in pq.read_table(path,columns=['raw_json']).column(0).to_pylist():
            r=json.loads(raw);by_expiry[r['underlying_symbol'],r['expiration_date']].add(r['symbol'])
    calendar={d['date']:d for d in read_calendar(w.CALENDAR)};actual=defaultdict(set);seen=set();count=0;edges=0;minutes=0
    for batch in pq.ParquetFile(root/seal['path']).iter_batches(batch_size=1000):
        for r in batch.to_pylist():
            day=calendar[r['session']];symbols=r['symbols'];key=(r['ticker'],r['session'])
            start=pd.Timestamp(day['date']+' '+day['open'],tz='America/New_York').value
            end=pd.Timestamp(day['date']+' '+day['close'],tz='America/New_York').value
            value={k:v for k,v in r.items() if k not in ('window_id','__index_level_0__')}
            if (r['window_id'] in seen or a.digest(value)!=r['window_id'] or not 1<=len(symbols)<=100
                or set(symbols)&actual[key] or symbols!=sorted(set(symbols))
                or r['start_ns']!=start or r['end_exclusive_ns']!=end
                or r['route']!='option_bars' or r['historical_eligibility_admitted']):raise ValueError('Window identity/membership drift')
            actual[key].update(symbols);seen.add(r['window_id']);count+=1;edges+=len(symbols);minutes+=len(symbols)*(end-start)//w.MINUTE
    for day in calendar:
        d=date.fromisoformat(day)
        for t in a.SYMBOLS:
            expected=set().union(*(by_expiry[t,str(d+timedelta(days=i))] for i in range(1,46)))
            if actual[t,day]!=expected:raise ValueError('Full context coverage mismatch')
    if (count,edges,minutes)!=(seal['queries'],seal['symbol_session_edges'],seal['requested_symbol_minutes']):raise ValueError('Context totals differ')
    result=dict(plan_sha256=p['sha256'],context_sha256=seal['sha256'],queries=count,symbol_session_edges=edges,
        requested_symbol_minutes=minutes,all_memberships_and_bounds_reconciled=True,
        auditor_sha256=a.sha(Path(__file__).read_bytes()),historical_admission=False)
    a.save(root/'CONTEXT_AUDIT.json',result);return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);args=p.parse_args();print(json.dumps(audit(args.root),indent=2))
