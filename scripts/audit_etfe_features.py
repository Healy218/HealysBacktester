"""Independently audit ETFE features v1: census, masks, causality (prefix) and sampled recomputation."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import feature_build as f,selection_v2 as s
from nn_meta.etfe.causal_inputs import stock_minutes,technical_diagnostics
from nn_meta.etfe.causal_pilot import STOCK
from nn_meta.etfe.label_build import SELECTION
from nn_meta.etfe import tv_features as tv

RNG=np.random.default_rng(20261007)


def audit_scope(root,tag,problems,sample=400):
    ticker,minutes=tag.split('-');minutes=int(minutes)
    t=pq.read_table(root/f'{tag}.parquet').to_pandas()
    sel=pq.read_table(SELECTION/f'{tag}.parquet',columns=['chart_row','right','target_dte','candidate','raw_spot','signal_at_ns']).to_pandas()
    sel=sel[sel.candidate!=''].reset_index(drop=True)
    if len(t)!=len(sel) or not (t.contract.to_numpy()==sel.candidate.to_numpy()).all():problems.append(f'{tag}: row census');return
    names,groups=f.fields()
    for n in names:
        if not ((t[n].isna().to_numpy())==(t['missing__'+n].to_numpy()==1)).all():problems.append(f'{tag}: mask {n}')
    masked=[n for n in names if n.startswith('param_')]+f.TRADE_MASKED
    if t[masked].notna().any().any():problems.append(f'{tag}: declared-masked field populated')
    chart=pd.read_parquet(s.SIGNALS/tag/'chart.parquet')
    # Causality: technical and TV on a truncated chart must equal stored values for rows before the cut.
    raw=stock_minutes(STOCK,ticker)
    for cut in sorted(RNG.choice(np.arange(len(chart)//3,len(chart)-10),2,replace=False)):
        prefix=chart.iloc[:cut];rows=t[t.chart_row<cut]
        tech=technical_diagnostics(prefix)
        for n in groups['technical']:
            if not np.allclose(tech[n].to_numpy()[rows.chart_row],rows[n],rtol=1e-12,atol=1e-12,equal_nan=True):problems.append(f'{tag}: technical prefix {n} cut {cut}')
        obs=prefix.index[np.unique(rows.chart_row)][-200:]
        v,_,_=tv.compute(prefix,raw[raw.index<prefix.bar_end.iloc[-1]],minutes,pd.DatetimeIndex(obs))
        stored=t[t.chart_row.isin(prefix.index.get_indexer(obs))].drop_duplicates('chart_row').set_index('chart_row')
        mine=v.reset_index(drop=True);mine.index=prefix.index.get_indexer(obs)
        for n in groups['tv']:
            a=stored[n].reindex(mine.index).to_numpy();b=mine[n].to_numpy()
            if not np.allclose(a,b,rtol=1e-9,atol=1e-12,equal_nan=True):problems.append(f'{tag}: tv prefix {n} cut {cut}');break
    # Sampled recomputation: firing fractions, identity, option bars.
    idx=RNG.choice(len(t),min(sample,len(t)),replace=False);bars,windows=f.load_bars(ticker)
    fam_bits={}
    for path in sorted((s.SIGNALS/tag).glob('*.npz')):
        if path.name.endswith('-union.npz'):continue
        with np.load(path,allow_pickle=False) as z:
            rows=int(z['rows'][0]);bits=np.unpackbits(z['packed'],axis=0,count=rows)
        fam=path.stem.rsplit('-',1)[0];fam_bits.setdefault(fam,[]).append(bits)
    contracts=pq.read_table(ROOT/'nn_meta/validation/etfe-dated-policy-20261006-r0/CONTRACTS.parquet',columns=['symbol','expiration_date','strike']).to_pandas().set_index('symbol')
    for i in idx:
        r=t.iloc[i];q=sel.iloc[i];ch=0 if r.right=='call' else 2
        for fam,arrs in fam_bits.items():
            fired=sum(int(a[r.chart_row,ch,:].sum()) if r.chart_row<len(a) else 0 for a in arrs);size=sum(a.shape[2] for a in arrs)
            if abs(fired/size-r['strat_'+fam])>1e-12:problems.append(f'{tag} row {i}: strat_{fam}');break
        k=contracts.loc[r.contract]
        if abs(np.log(k.strike/q.raw_spot)-r.moneyness)>1e-12:problems.append(f'{tag} row {i}: moneyness')
        day=pd.Timestamp(r.signal_at_ns,tz='UTC').tz_convert('America/New_York').date()
        if abs((k.expiration_date-day).days/5-r.dte_frac)>1e-12:problems.append(f'{tag} row {i}: dte_frac')
        b=bars.get(r.contract);lo,hi=windows[r.contract];end=r.signal_at_ns-60_000_000_000;start=end-minutes*60_000_000_000
        if lo<=start and end<=hi:
            m=(b[0]>=start)&(b[0]<end) if b is not None else np.array([],bool)
            n=int(m.sum());cps=float(b[2][m].sum())/(60*minutes) if n else 0.0
            if abs(n/minutes-r.etfe_option_traded_bar_fraction)>1e-12 or abs(cps-r.etfe_option_trade_count_per_second)>1e-9:
                problems.append(f'{tag} row {i}: option bars')
        elif not np.isnan(r.etfe_option_traded_bar_fraction):problems.append(f'{tag} row {i}: uncaptured window populated')


def audit(root):
    root=Path(root);problems=[];scopes=[]
    for path in sorted(root.glob('*-*.parquet')):
        audit_scope(root,path.stem,problems);scopes.append(path.stem)
    result=dict(schema='etfe-features-v1-independent-audit',scopes=scopes,problems=problems[:100],passed=not problems)
    (root/'INDEPENDENT_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(audit(args.root.resolve()),indent=2))
