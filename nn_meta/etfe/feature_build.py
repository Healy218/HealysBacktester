"""ETFE full feature build v1 for decision-clock rows (SPY/QQQ), registered 221 values + 221 masks.

Reuses the audited producers (causal_inputs.technical_diagnostics, tv_features.compute,
context_features.daily_stock/stock_context/proxy_iv/option_context, purchase_policy_v2.dte_fraction)
under ETFE_FEATURE_AMENDMENT_20261007:
- static: strat_<family> = fraction of that family's variants firing the row's entry channel at the
  bar; timeframe one-hots; param_* masked (row_unit_amendment);
- signal: dir_short from right; bars_since_signal = log1p(bars since this scope's previous decision
  bar on the same right); ma_gap/px_vs_fast = median over firing MA-family variants' own windows,
  masked when none fired;
- option: bars-only. Bar fields from captured minute bars, where complete terminal capture of the
  window is the no-trade evidence; trade count/volume per second from bar n/v (no condition
  allowlist); range, size CV, VWAP-vs-last and tick-rule fields masked (bars_only_first_run);
- daily option context from census daily bars (daily close as premium; freshness unverifiable),
  far tenor and put/call ratio masked where census expiries (<= 2026-10-09) cannot cover 45 DTE;
- identity: dte_frac, moneyness = log(K/S); sector idx_etf for SPY and QQQ.
"""
from collections import defaultdict
import datetime as dt
import json
import math
from pathlib import Path
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from nn_meta.etfe import existence_census as x,option_daily_capture as o,selection_v2 as s
from nn_meta.etfe.causal_inputs import stock_minutes,technical_diagnostics
from nn_meta.etfe.causal_pilot import SETUP,STOCK
from nn_meta.etfe.context_features import OPTION_FIELDS,STOCK_FIELDS,daily_stock,option_context,proxy_iv,stock_context
from nn_meta.etfe.joined_features import schema
from nn_meta.etfe.label_build import BARS,BARS_RAW,COLUMNS,SELECTION
from nn_meta.etfe.purchase_policy_v2 import dte_fraction
from nn_meta.etfe import tv_features as tv

ROOT=Path(__file__).resolve().parents[2]
MINUTE=60_000_000_000
LAST_EXPIRY=x.LAST_EXPIRY
TRADE_MASKED=['etfe_option_trade_range_bps','etfe_option_trade_size_cv','etfe_option_vwap_last_bps',
    'etfe_option_tickrule_signed_volume_fraction','etfe_option_tickrule_classified_volume_fraction']
SECTOR={'SPY':'idx_etf','QQQ':'idx_etf'}
CHUNK=500_000


def fields():
    sc=schema();return sc['fields'],sc['groups']


# ---- daily context ---------------------------------------------------------------------------
def census_daily():
    """All census daily option bars: symbol, session date, close, volume, trade count."""
    rows=[]
    for item in o.load_plan(s.CENSUS)['jobs']:
        for _,body,_ in o.committed(s.CENSUS,item)[0]:
            for sym,r in o.rows(body,item):
                rows.append((sym,pd.Timestamp(r['t']).tz_convert('America/New_York').date(),float(r['c']),int(r['v']),int(r['n'])))
    d=pd.DataFrame(rows,columns=['symbol','session_date','close','volume','trades'])
    d['ticker']=d.symbol.str[:3];d['expiry']=pd.to_datetime('20'+d.symbol.str[3:9],format='%Y%m%d').dt.date
    d['right']=np.where(d.symbol.str[9]=='C','call','put');d['strike']=d.symbol.str[10:].astype(int)/1000
    return d


def daily_surface(census,ticker,daily):
    """Daily-close variant of context_features.surface_summary (declared deviation)."""
    c=census[census.ticker==ticker];by_day={k:g for k,g in c.groupby('session_date')};rows=[];why=[]
    for day,row in daily.iterrows():
        spot=row.close;g=by_day.get(dt.date.fromisoformat(day) if isinstance(day,str) else day)
        empty=dict(near=np.nan,far=np.nan,ratio=np.nan)
        if g is None or not math.isfinite(spot) or spot<=0:rows.append(empty);why.append('no_census_session');continue
        d=dt.date.fromisoformat(day) if isinstance(day,str) else day
        g=g.assign(dte=[(e-d).days for e in g.expiry]);g=g[(g.dte>=1)&(g.dte<=45)&(g.trades>=1)]
        near_ok=(d+dt.timedelta(days=20))<=LAST_EXPIRY;far_ok=(d+dt.timedelta(days=45))<=LAST_EXPIRY
        vol=g[g.close>=.20].groupby('right').volume.sum()
        atm=g[(g.close>=.20)&(np.abs(np.log(g.strike/spot))<.01)];near=[];far=[]
        for r in atm.itertuples():
            iv,_=proxy_iv(r.close,spot,r.strike,int(r.dte),r.right)
            if math.isfinite(iv):(near if r.dte<=20 else far).append(iv)
        call,put=vol.get('call',0),vol.get('put',0)
        rows.append(dict(near=float(np.median(near)) if near and near_ok else np.nan,
            far=float(np.median(far)) if far and far_ok else np.nan,
            ratio=float(np.clip(put/call,0,5)) if call>0 and far_ok else np.nan))
        why.append('census_daily_close' if far_ok else 'census_expiry_horizon')
    return pd.DataFrame(rows,index=daily.index),why


def daily_context(ticker,census):
    """Per session: 3 stock + 7 option context fields, available at the next session open."""
    spy=daily_stock(pd.read_parquet(s.SIGNALS/'SPY-1/chart.parquet'))
    own=spy if ticker=='SPY' else daily_stock(pd.read_parquet(s.SIGNALS/f'{ticker}-1/chart.parquet'))
    stock,_=stock_context(own,spy)
    surf,_=daily_surface(census,ticker,own);spy_surf,_=daily_surface(census,'SPY',spy)
    opt=option_context(surf,spy_surf,stock)
    return pd.concat([stock,opt],axis=1)


# ---- per-scope pieces ------------------------------------------------------------------------
def firing(tag,catalog):
    """Per right: family firing fractions (bars x families) and per-bar MA median ma_gap/px_vs_fast."""
    folder=s.SIGNALS/tag;chart=pd.read_parquet(folder/'chart.parquet');n=len(chart);close=chart.Close.to_numpy()
    by_id={r['variant_id']:r for r in catalog};families=sorted({r['strategy'] for r in catalog})
    counts={r:np.zeros((n,len(families)),np.float64) for r in ('call','put')};sizes=np.zeros(len(families))
    means={};ma={'call':([],[],[]),'put':([],[],[])}
    for path in sorted(folder.glob('*.npz')):
        if path.name.endswith('-union.npz'):continue
        fam=path.stem.rsplit('-',1)[0];fi=families.index(fam)
        with np.load(path,allow_pickle=False) as z:
            rows=int(z['rows'][0]);bits=np.unpackbits(z['packed'],axis=0,count=rows);ids=z['variants'].tolist()
        sizes[fi]+=len(ids)
        for right,ch in (('call',0),('put',2)):
            counts[right][:rows,fi]+=bits[:,ch,:].sum(axis=1)
            if fam!='ma':continue
            for v,vid in enumerate(ids):
                pos=np.flatnonzero(bits[:,ch,v])
                if not len(pos):continue
                p=by_id[vid]['params'];f,sl=int(p['fast_window']),int(p['slow_window'])
                for w in (f,sl):
                    if w not in means:means[w]=chart.Close.rolling(w).mean().to_numpy()
                ma[right][0].append(pos);ma[right][1].append((means[f][pos]-means[sl][pos])/close[pos]);ma[right][2].append(close[pos]/means[f][pos]-1)
    out={}
    for right in ('call','put'):
        frac=counts[right]/np.where(sizes>0,sizes,np.nan)
        if ma[right][0]:
            m=pd.DataFrame(dict(pos=np.concatenate(ma[right][0]),gap=np.concatenate(ma[right][1]),px=np.concatenate(ma[right][2])))
            med=m.groupby('pos')[['gap','px']].median()
        else:med=pd.DataFrame(columns=['gap','px'])
        out[right]=dict(frac=frac,ma=med)
    return chart,families,out


def option_bar_features(bars,lo,hi,signal_ns,minutes):
    """Bars-only window [t-(m+1) min, t-1 min): complete capture of the window is no-trade evidence."""
    end=signal_ns-MINUTE;start=end-minutes*MINUTE;nan=np.nan
    if not (lo<=start and end<=hi):return dict(frac=nan,age=nan,bps=nan,cps=nan,vps=nan),'uncaptured_window'
    i,j=np.searchsorted(bars[0],start),np.searchsorted(bars[0],end)
    n=j-i;sec=60*minutes
    age=(signal_ns-(int(bars[0][j-1])+MINUTE))/1e9 if n else nan
    return dict(frac=n/minutes,age=age,bps=n/sec,cps=float(bars[2][i:j].sum())/sec,vps=float(bars[1][i:j].sum())/sec),'observed_bars_only'


def load_bars(ticker):
    seal=json.loads((BARS/'NORMALIZED.json').read_text());tables=[]
    import pyarrow.compute as pc
    for key in seal['partition_receipts']:
        meta=json.loads((BARS/'partitions'/(key+'.json')).read_text())
        t=pq.read_table(BARS/meta['data'],columns=['symbol','timestamp_ns','volume','trade_count'])
        t=t.filter(pc.starts_with(t['symbol'],ticker))
        if t.num_rows:tables.append(t)
    t=pa.concat_tables(tables).to_pandas().sort_values(['symbol','timestamp_ns'],kind='stable');out={}
    for sym,g in t.groupby('symbol',sort=False):out[sym]=(g.timestamp_ns.to_numpy(),g.volume.to_numpy(),g.trade_count.to_numpy())
    windows={}
    from nn_meta.etfe import option_minute_capture as m
    for job in m.load_plan(BARS_RAW)['jobs']:
        lo,hi=pd.Timestamp(job['params']['start']).value,pd.Timestamp(job['params']['end']).value+1
        for sym in job['params']['symbols'].split(','):
            if sym.startswith(ticker):windows[sym]=(lo,hi)
    return out,windows


def build_scope(ticker,minutes,out,context,bars,windows,catalog):
    names,groups=fields();tag=f'{ticker}-{minutes}';started=time.monotonic()
    chart,families,fire=firing(tag,catalog)
    sel=pq.read_table(SELECTION.joinpath(tag+'.parquet'),columns=COLUMNS+['raw_spot']).to_pandas()
    decision_bars={r:np.unique(sel[sel.right==r].chart_row.to_numpy()) for r in ('call','put')}
    rows=all_rows=sel[sel.candidate!=''].reset_index(drop=True)
    tech=technical_diagnostics(chart)
    obs=chart.index[np.unique(rows.chart_row.to_numpy())]
    raw=stock_minutes(STOCK,ticker);tvv,_,_=tv.compute(chart,raw,minutes,pd.DatetimeIndex(obs))
    tvv=tvv.reindex(chart.index);t_ns=chart.bar_end.astype('int64').to_numpy()
    contracts=pq.read_table(ROOT/'nn_meta/validation/etfe-dated-policy-20261006-r0/CONTRACTS.parquet',columns=['symbol','expiration_date','strike']).to_pandas().set_index('symbol')
    col={n:i for i,n in enumerate(names)};dest=Path(out)/f'{tag}.parquet';writer=None;filled=np.zeros(len(names));total=len(rows)
    tech_np={n:tech[n].to_numpy() for n in groups['technical']};tv_np={n:tvv[n].to_numpy() for n in groups['tv']}
    for c0 in range(0,total,CHUNK):
        rows=all_rows.iloc[c0:c0+CHUNK].reset_index(drop=True)
        values=np.full((len(rows),len(names)),np.nan)
        # chart-level groups by row
        cr=rows.chart_row.to_numpy()
        for n in groups['technical']:values[:,col[n]]=tech_np[n][cr]
        for n in groups['tv']:values[:,col[n]]=tv_np[n][cr]
        ctx=context.reindex(rows.session_date.astype(str).to_numpy())
        for n in STOCK_FIELDS+OPTION_FIELDS:values[:,col[n]]=ctx[n].to_numpy()
        # static
        for right in ('call','put'):
            m=(rows.right==right).to_numpy();fr=fire[right]['frac'][cr[m]]
            for fi,fam in enumerate(families):values[m,col['strat_'+fam]]=fr[:,fi]
            med=fire[right]['ma'].reindex(cr[m])
            values[m,col['ma_gap']]=med.gap.to_numpy();values[m,col['px_vs_fast']]=med.px.to_numpy()
            db=decision_bars[right];k=np.searchsorted(db,cr[m]);prev=np.where(k>0,db[np.maximum(k-1,0)],-1)
            values[m,col['bars_since_signal']]=np.where(prev>=0,np.log1p(cr[m]-prev),np.nan)
        for tf in (1,5,15):values[:,col[f'timeframe_{tf}']]=float(minutes==tf)
        values[:,col['dir_short']]=(rows.right=='put').to_numpy().astype(float)
        for sec in ('idx_etf','sec_etf','tech','semis','fin','crypto','defensive','cyclical','spec'):values[:,col['sec_'+sec]]=float(SECTOR[ticker]==sec)
        # identity + option bars per row
        at=pd.to_datetime(rows.signal_at_ns,utc=True)
        exp=contracts.expiration_date.reindex(rows.candidate).to_numpy();strike=contracts.strike.reindex(rows.candidate).to_numpy()
        values[:,col['moneyness']]=np.log(strike/rows.raw_spot.to_numpy())
        values[:,col['dte_frac']]=[(e-a.tz_convert('America/New_York').date()).days/5 for e,a in zip(exp,at)]
        ob=defaultdict(list)
        for sym,sig in zip(rows.candidate,rows.signal_at_ns):
            b=bars.get(sym,(np.array([],np.int64),np.array([]),np.array([])));lo,hi=windows.get(sym,(0,0))
            f,_=option_bar_features(b,lo,hi,int(sig),minutes)
            for k_,v in f.items():ob[k_].append(v)
        for k_,n in (('frac','etfe_option_traded_bar_fraction'),('age','etfe_option_bar_end_age_seconds'),('bps','etfe_option_traded_bars_per_second'),
                     ('cps','etfe_option_trade_count_per_second'),('vps','etfe_option_trade_volume_per_second')):values[:,col[n]]=np.array(ob[k_])
        # param_* and trade-only option fields stay NaN (masked) by declaration.
        keys=pa.table(dict(ticker=rows.ticker,minutes=rows.minutes,chart_row=rows.chart_row,signal_at_ns=rows.signal_at_ns,
            right=rows.right,target_dte=rows.target_dte,contract=rows.candidate))
        cols={n:pa.array(values[:,i]) for n,i in col.items()}
        cols.update({'missing__'+n:pa.array(np.isnan(values[:,i]).astype(np.uint8)) for n,i in col.items()})
        table=pa.Table.from_arrays(list(keys.columns)+list(cols.values()),names=keys.column_names+list(cols))
        if writer is None:writer=pq.ParquetWriter(dest,table.schema,compression='zstd')
        writer.write_table(table,row_group_size=200000);filled+=(~np.isnan(values)).sum(axis=0)
    writer.close();filled=filled/max(total,1)
    return dict(scope=tag,rows=total,elapsed_seconds=time.monotonic()-started,
        fill_by_field={n:round(float(filled[i]),4) for n,i in col.items()},data=dest.name)
