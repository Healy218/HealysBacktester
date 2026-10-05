"""Independent catalog, rolling-context, event-age and membership reconciliation."""
import argparse,gzip,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from nn_meta.etfe.acquisition import sha,save
from nn_meta.etfe.remaining_feature_pilot import verify,PILOT,catalog


def check_value(row,name,expected,reason):
    actual=row['diagnostic__'+name];missing=row['missing__diagnostic__'+name]
    assert missing==int(pd.isna(actual))==int(pd.isna(expected)),(name,actual,expected)
    assert row['reason__'+name]==reason,(name,row['reason__'+name],reason)
    if not missing:assert math.isclose(actual,expected,rel_tol=1e-12,abs_tol=1e-12),(name,actual,expected)


def checked(root,f):
    assert sha((root/f['path']).read_bytes())==f['sha256']
    return pd.read_parquet(root/f['path']) if f['path'].endswith('.parquet') else None


def audit(root):
    root=Path(root).resolve();plan=verify(root);complete=json.load(open(root/'COMPLETE.json'))
    assert complete['complete'] and complete['plan_sha256']==plan['sha256']
    assert sha((root/'SHARED.json').read_bytes())==complete['shared_sha256']
    shared=json.load(open(root/'SHARED.json'));frames=[checked(root,f) for f in shared['files']]
    static,context,source=frames[:3];records={r['variant_id']:r for r in catalog()}
    assert set(static.index)==set(records) and len(static)==8451
    snames=[n[12:] for n in static if n.startswith('diagnostic__')];assert len(snames)==77
    static_cells=0
    for vid,row in static.to_dict('index').items():
        record=records[vid];params=record['params']
        for n in snames:
            if n.startswith('strat_'):expected=float(record['strategy']==n[6:])
            elif n.startswith('timeframe_'):expected=float(record['signal_minutes']==int(n[10:]))
            elif n in ['param_setup_'+s for s in ('BRT','DIV','EMA','ORB','SWEEP','VWAP')]:
                expected=float(params['setup_identity']==n[12:]) if 'setup_identity' in params else math.nan
            else:expected=float(params[n[6:]]) if n[6:] in params else math.nan
            check_value(row,n,expected,'structural_absence' if pd.isna(expected) else 'catalog_identity');static_cells+=1
    assert len(context)==len(source)==2073
    cnames=[n[12:] for n in context if n.startswith('diagnostic__')];assert len(cnames)==10
    spy=source[source.ticker.eq('SPY')].reset_index(drop=True);daily_finite=0;daily_missing=0
    for ticker in ('SPY','QQQ','VOO'):
        daily=source[source.ticker.eq(ticker)].reset_index(drop=True);out=context[context.ticker.eq(ticker)].reset_index(drop=True)
        assert len(out)==691 and out.session_date.tolist()==daily.session_date.tolist()==spy.session_date.tolist()
        assert out.available_at.tolist()==daily.session_open.tolist()
        closes=daily.close.to_numpy();market=spy.close.to_numpy()
        for i,row in enumerate(out.to_dict('records')):
            for n in cnames:
                v=math.nan
                if n in ('rvol_5','rvol_21','beta_60d'):
                    period=60 if n=='beta_60d' else int(n.split('_')[1])
                    if i>=period+1:
                        x=closes[i-period-1:i];m=market[i-period-1:i]
                        if np.isfinite(x).all() and (n!='beta_60d' or np.isfinite(m).all()):
                            if n!='beta_60d':v=float(np.std(np.diff(np.log(x)),ddof=1)*math.sqrt(252))
                            else:
                                xr=x[1:]/x[:-1]-1;mr=m[1:]/m[:-1]-1
                                variance=float(np.var(mr,ddof=1))
                                if variance>0:v=float(np.cov(xr,mr,ddof=1)[0,1]/variance)
                    reason='observed_raw_unadmitted' if math.isfinite(v) else 'insufficient_complete_daily_history_or_zero_variance'
                else:reason='dated_surface_coverage_unresolved'
                check_value(row,n,v,reason);daily_finite+=int(math.isfinite(v));daily_missing+=int(not math.isfinite(v))
    logical=signal_count=pre_pilot=0
    for scope in plan['scopes']:
        name=f"{scope['ticker']}-{scope['minutes']}.json";assert sha((root/name).read_bytes())==complete['scope_receipts'][name]
        r=json.load(open(root/name));assert r['plan_sha256']==plan['sha256'] and r['prefix_batch_passed']
        sf,links,_=[checked(root,f) for f in r['files']]
        positions=json.loads(gzip.decompress((root/r['files'][2]['path']).read_bytes()))
        bars=pd.read_parquet(PILOT/scope['underlying']['path']);bars=bars[bars.bar_end.le(pd.Timestamp('2024-01-19T21:00Z'))]
        at=pd.DatetimeIndex(bars.bar_end).as_unit('ns').asi8;close=bars.Close.to_numpy()
        expected={};keys=set()
        for h in positions:
            key=(h['variant_id'],h['direction']);assert key not in keys;keys.add(key)
            assert h['positions']==sorted(set(h['positions'])) and all(0<=p<len(bars) for p in h['positions'])
            previous=-1
            for p in h['positions']:
                if at[p]>=pd.Timestamp('2024-01-18T14:30Z').value:expected[(key[0],key[1],int(at[p]))]=(p,previous)
                previous=p
        vids={vid for vid,rec in records.items() if rec['signal_minutes']==scope['minutes']}
        assert keys=={(vid,d) for vid in vids for d in ('long','short')}
        assert len(expected)==len(sf) and not sf.duplicated(['variant_id','direction','signal_at_ns']).any()
        for row in sf.to_dict('records'):
            p,previous=expected.pop((row['variant_id'],row['direction'],row['signal_at_ns']))
            assert p==row['bar_position'] and previous==row['previous_position']
            assert row['previous_signal_at_ns']==(int(at[previous]) if previous>=0 else -1)
            rec=records[row['variant_id']];assert rec['strategy']==row['strategy']
            check_value(row,'dir_short',float(row['direction']=='short'),'observed_diagnostic')
            check_value(row,'bars_since_signal',math.log1p(p-previous) if previous>=0 else math.nan,'observed_diagnostic' if previous>=0 else 'first_signal')
            fast,slow=(rec['params']['fast_window'],rec['params']['slow_window']) if rec['strategy']=='ma' else (10,30)
            a=float(np.mean(close[p-fast+1:p+1])) if p+1>=fast else math.nan
            b=float(np.mean(close[p-slow+1:p+1])) if p+1>=slow else math.nan
            for n,v in (('ma_gap',(a-b)/close[p]),('px_vs_fast',close[p]/a-1)):
                check_value(row,n,v,'observed_diagnostic' if math.isfinite(v) else 'insufficient_chart_history')
            pre_pilot+=int(previous>=0 and at[previous]<pd.Timestamp('2024-01-18T14:30Z').value)
        assert not expected
        events=pd.read_parquet(PILOT/scope['events']['path'])
        assert len(links)==len(events)==r['logical_rows'] and links.event_ordinal.tolist()==list(range(len(events)))
        assert links.signal_ordinal.between(0,len(sf)-1).all()
        mapped=sf.iloc[links.signal_ordinal].reset_index(drop=True)
        for n in ('variant_id','direction','signal_at_ns','strategy'):assert mapped[n].tolist()==events[n].tolist()
        assert links.variant_id.tolist()==events.variant_id.tolist()
        days=pd.to_datetime(events.signal_at_ns,utc=True).dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
        assert links.context_session_date.tolist()==days.tolist()
        assert set(days).issubset(set(context[context.ticker.eq(scope['ticker'])].session_date))
        for n in [n[12:] for n in links if n.startswith('diagnostic__')]:
            assert links['diagnostic__'+n].isna().all() and links['missing__diagnostic__'+n].eq(1).all()
            assert links['reason__'+n].eq('dated_selected_contract_unresolved' if n in ('dte_frac','moneyness') else 'dated_sector_unresolved').all()
        for frame in (static,context,sf,links):
            assert not frame.model_feature_admitted.any()
            for n in frame:
                if n.startswith('diagnostic__'):assert str(frame[n].dtype)=='float64'
                if n.startswith('missing__diagnostic__'):assert str(frame[n].dtype)=='uint8'
        logical+=len(links);signal_count+=len(sf)
    assert logical==complete['logical_rows']==458133 and signal_count==complete['signals']==152711
    assert pre_pilot==complete['signals_with_pre_pilot_prior']
    result=dict(schema='etfe-remaining-components-independent-audit-v1',plan_sha256=plan['sha256'],
        auditor_sha256=sha(Path(__file__).read_bytes()),complete_sha256=sha((root/'COMPLETE.json').read_bytes()),
        fields=100,static_variants=8451,static_cells=static_cells,daily_rows=2073,daily_finite=daily_finite,daily_missing=daily_missing,
        signals=signal_count,logical_rows=logical,signals_with_pre_pilot_prior=pre_pilot,
        all_values_masks_reasons_reconciled=True,all_logical_memberships_reconciled=True,
        option_surface_real_numerical_validation=False,model_feature_admitted=False,full_feature_schema_complete=False,ready_for_training=False)
    save(root/'INDEPENDENT_AUDIT.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    print(json.dumps(audit(p.parse_args().root),indent=2))
