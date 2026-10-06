"""Independently recompute ETFE dated-input policy v1 outputs and candidate availability coverage."""
import argparse
import datetime as dt
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import acquisition as a
from nn_meta.etfe import dated_policy as d


def expected_status(symbol,mult,size,deliv):
    # Separate formulation: parse fields positionally rather than via the module regex.
    root=symbol[:3]
    if root not in d.UNDERLYINGS or len(symbol)!=18 or not symbol[3:9].isdigit() or symbol[9] not in 'CP' or not symbol[10:].isdigit():
        return 'excluded'
    x=json.loads(deliv)
    ok=(len(x)==1 and x[0]['type']=='equity' and x[0]['symbol']==root and x[0]['amount']=='100'
        and x[0]['allocation_percentage']=='100' and size=='100' and mult in ('100','0'))
    return 'admitted' if ok else 'excluded'


def recompute_first():
    tables=[]
    for name in d.OPTION_ROOTS:
        for meta_path in (d.CACHE/name/'partitions').glob('*.json'):
            meta=json.loads(meta_path.read_text())
            if meta['route'] in ('option_bars','option_trades') and meta['rows']:
                t=pq.read_table(d.CACHE/name/meta['data'],columns=['symbol','timestamp_ns'])
                off=d.BAR_NS if meta['route']=='option_bars' else 0
                tables.append(pa.table({'symbol':t['symbol'],'t':pc.add(t['timestamp_ns'],off)}))
    pilot=a.load_plan(d.SOURCES['window_checks'])
    syms=[];ts=[]
    for item in pilot['jobs']:
        if item['route'] in ('option_bars','option_trades'):
            off=d.BAR_NS if item['route']=='option_bars' else 0
            for _,body,_ in a.committed(d.SOURCES['window_checks'],item)[0]:
                for s,row in a.rows(body,item):syms.append(s);ts.append(pd.Timestamp(row['t']).value+off)
    tables.append(pa.table({'symbol':pa.array(syms,pa.string()),'t':pa.array(ts,pa.int64())}))
    g=pa.concat_tables(tables).group_by('symbol').aggregate([('t','min')])
    return dict(zip(g['symbol'].to_pylist(),g['t_min'].to_pylist()))


def audit(root):
    root=Path(root);summary=json.loads((root/'RESOLUTION.json').read_text())
    table=pq.read_table(root/'CONTRACTS.parquet').to_pandas()
    if a.sha((root/'CONTRACTS.parquet').read_bytes())!=summary['contracts_sha256']:raise ValueError('Contracts hash')
    for path,digest in summary['sources'].items():
        if a.sha((ROOT/path).read_bytes())!=digest:raise ValueError(f'Source drift {path}')
    census=d.census_contracts().set_index('symbol')
    if set(census.index)!=set(table.symbol):raise ValueError('Contract census mismatch')
    c=census.loc[table.symbol]
    exp=[expected_status(s,m,z,j) for s,m,z,j in zip(table.symbol,c.multiplier_raw,c.size_raw,c.deliverables_json)]
    if exp!=table.status.tolist():raise ValueError('Economics status mismatch')
    adm=table[table.status=='admitted']
    if not ((adm.multiplier==100)&(adm.deliverable_shares==100)).all():raise ValueError('Admitted economics')
    # Settlement equals provider calendar entry for the expiry date.
    cal=json.loads((d.SOURCES['calendar']/'000-calendar.body').read_bytes())
    provider={r['date']:r['settlement_date'] for r in cal}
    got=[None if v is None else str(v) for v in table.exercise_settlement_date]
    want=[None if e is None else provider.get(str(e)) for e in table.expiration_date]
    if got!=want:raise ValueError('Settlement lookup mismatch')
    first=recompute_first()
    fa=pq.read_table(root/'CONTRACTS.parquet',columns=['first_available_ns'])['first_available_ns'].to_pylist()
    if fa!=[first.get(s) for s in table.symbol]:raise ValueError('First-available mismatch')
    # Actions: next trading session after declaration via searchsorted.
    days=np.array([np.datetime64(r['date']) for r in cal])
    for x in json.loads((root/'ACTIONS.json').read_text()):
        i=np.searchsorted(days,np.datetime64(x['declaration_date']),side='right')
        if str(days[i])!=x['known_from_session']:raise ValueError('Action known session mismatch')
        if (x['symbol'],x['ex_date'])==d.QQQ_PAYABLE_OVERRIDE and x['payable_date']!='2024-04-30':raise ValueError('QQQ payable')
    gaps=json.loads((root/'VOO_GAPS.json').read_text())['gap_ns']
    wc=json.loads((d.SOURCES['window_checks']/'WINDOW_CHECK_AUDIT.json').read_text())
    if gaps!=sorted(pd.Timestamp(g['timestamp']).value for g in wc['gap_results']):raise ValueError('Gap mismatch')
    # Consequence check: candidate decision rows whose contract is available by entry start.
    avail=dict(zip(table.symbol,fa));cov={}
    for f in sorted(glob.glob(str(ROOT/'nn_meta/validation/etfe-exact-windows-20261006-r0/*-*.parquet'))):
        w=pq.read_table(f,columns=['acquisition_candidate','entry_start_ns']).to_pandas()
        w=w[w.acquisition_candidate.fillna('')!='']
        ok=sum(avail.get(s) is not None and avail[s]<=e for s,e in zip(w.acquisition_candidate,w.entry_start_ns))
        cov[Path(f).stem]=dict(candidates=len(w),available_by_entry_start=ok)
    result=dict(schema='etfe-dated-policy-independent-audit-v1',resolution_sha256=a.sha((root/'RESOLUTION.json').read_bytes()),
        contracts=len(table),admitted=len(adm),first_available_symbols=sum(v is not None for v in fa),
        actions=summary['actions'],voo_gaps=len(gaps),candidate_availability=cov,
        candidates_total=sum(v['candidates'] for v in cov.values()),
        candidates_available=sum(v['available_by_entry_start'] for v in cov.values()),
        all_recomputations_match=True,ready_for_build=False,ready_for_training=False,
        auditor_sha256=a.sha(Path(__file__).read_bytes()))
    a.save(root/'INDEPENDENT_AUDIT.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(audit(args.root.resolve()),indent=2))
