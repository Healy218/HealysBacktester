"""Independent all-window numerical and logical-membership reconciliation."""
from collections import Counter
import argparse,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from nn_meta.etfe.acquisition import sha,save,digest
from nn_meta.etfe.option_feature_pilot import verify,market_inputs,PILOT
from nn_meta.etfe.option_features import NAMES,MINUTE


def independent(symbol,at,m,inside,coverage,trades,bars):
    values=[None]*10;reasons=['uncomputed']*10
    if not inside:return values,['outside_stock_session_option_hours_unresolved']*10
    lo=at-(m+1)*MINUTE;hi=at-MINUTE
    tr=[r for t in range(lo,hi,MINUTE) for r in trades.get((symbol,t),[])]
    br=[r for t in range(lo,hi,MINUTE) for r in bars.get((symbol,t),[])]
    # This audit is deliberately scoped to the actual fixture: no no-trade
    # evidence, all observed codes allowed, no native IDs or delayed publication.
    assert all(r['condition'] in 'HIJSabcdefghijklmnopqrs' and r['native_trade_id'] is None and not r['quality_flags'] and r['price']>0 and r['size']>0 for r in tr)
    assert all(not r['quality_flags'] and r['vwap']>0 and r['volume']>0 and r['trade_count']>0 for r in br)
    assert len({r['timestamp_ns'] for r in br})==len(br)
    trade_ok=all(trades.get((symbol,t)) for t in range(lo,hi,MINUTE))
    bar_ok=all(bars.get((symbol,t)) for t in range(lo,hi,MINUTE))
    assert all(coverage.get((symbol,t),{}).get('trade_transport_complete') and coverage[(symbol,t)]['bar_transport_complete'] for t in range(lo,hi,MINUTE))
    for i in (0,1,5,6,7,8,9):reasons[i]='observed_diagnostic' if trade_ok else 'unresolved_absence'
    for i in (2,3,4):reasons[i]='observed_diagnostic' if bar_ok else 'unresolved_absence'
    if trade_ok:
        ordered=sorted(tr,key=lambda r:r['timestamp_ns']);prices=[r['price'] for r in ordered];sizes=[r['size'] for r in ordered]
        volume=sum(sizes);avg=volume/len(sizes);vwap=math.fsum(p*s for p,s in zip(prices,sizes))/volume
        values[0]=10000*(max(prices)-min(prices))/vwap
        values[1]=math.sqrt(math.fsum((s-avg)**2 for s in sizes)/len(sizes))/avg
        values[5]=len(tr)/(60*m);values[6]=volume/(60*m)
        latest={r['price'] for r in ordered if r['timestamp_ns']==ordered[-1]['timestamp_ns']}
        if len(latest)==1:
            last=next(iter(latest));values[7]=10000*(vwap-last)/last
        else:reasons[7]='ambiguous_last_trade'
        if len({r['timestamp_ns'] for r in ordered})!=len(ordered):reasons[8]=reasons[9]='ambiguous_order'
        else:
            previous=None;sign=0;signed=classified=0
            for p,s in zip(prices,sizes):
                if previous is not None and p!=previous:sign=1 if p>previous else -1
                signed+=sign*s;classified+=s if sign else 0;previous=p
            values[8]=signed/volume;values[9]=classified/volume
    if bar_ok:
        values[2]=len(br)/m;values[3]=(at-max(r['timestamp_ns']+MINUTE for r in br))/1e9;values[4]=len(br)/(60*m)
    return values,reasons


def audit(root):
    root=Path(root).resolve();plan=verify(root);complete=json.loads((root/'COMPLETE.json').read_text())
    assert complete['complete'] and len(complete['scope_receipts'])==9 and complete['plan_sha256']==plan['sha256']
    coverage,trades,bars=market_inputs();logical=candidates=windows=all_finite=0
    physical_reasons={n:Counter() for n in NAMES};logical_reasons={n:Counter() for n in NAMES};samples=[]
    for scope in plan['scopes']:
        name=f"{scope['ticker']}-{scope['minutes']}.json";path=root/name
        assert sha(path.read_bytes())==complete['scope_receipts'][name]
        r=json.loads(path.read_text());assert r['plan_sha256']==plan['sha256']
        for f in r['files']:assert sha((root/f['path']).read_bytes())==f['sha256']
        frame=pd.read_parquet(root/r['files'][0]['path']);links=pd.read_parquet(root/r['files'][1]['path'])
        events=pd.read_parquet(PILOT/scope['events']['path'])
        assert len(links)==len(events)==r['logical_rows'] and links.event_ordinal.tolist()==list(range(len(events)))
        assert not links.model_feature_admitted.any() and not frame.model_feature_admitted.any()
        assert frame.window_id.is_unique and not frame.duplicated(['symbol','signal_at_ns','minutes']).any()
        indexed=frame.set_index('window_id');expected_ids=[]
        for e in events.itertuples():
            if e.acquisition_candidate is None:expected_ids.append(None);continue
            wid=digest([e.acquisition_candidate,e.signal_at_ns,e.minutes]);expected_ids.append(wid)
            w=indexed.loc[wid]
            assert w.feature_start_ns==e.feature_start_ns and w.feature_end_ns==e.feature_end_ns
            assert w.inside_stock_session==e.feature_inside_stock_session
        assert links.window_id.tolist()==expected_ids
        assert set(frame.window_id)==set(x for x in expected_ids if x is not None)
        weights=links.window_id.value_counts()
        for w in frame.to_dict('records'):
            expected,reasons=independent(w['symbol'],w['signal_at_ns'],w['minutes'],w['inside_stock_session'],coverage,trades,bars)
            finite=0
            for n,v,reason in zip(NAMES,expected,reasons):
                actual=w['diagnostic__'+n];missing=w['missing__diagnostic__'+n]
                assert missing==int(v is None)==int(pd.isna(actual)) and w['reason__'+n]==reason
                if v is not None:
                    assert np.isclose(actual,v,rtol=1e-12,atol=1e-12),(n,actual,v);finite+=1
                physical_reasons[n][reason]+=1;logical_reasons[n][reason]+=int(weights[w['window_id']])
            all_finite+=int(finite==10)
        for n in NAMES:logical_reasons[n]['no_prior_date_observed_candidate']+=int(links.window_id.isna().sum())
        logical+=len(links);candidates+=int(links.window_id.notna().sum());windows+=len(frame)
        samples.append(dict(scope=r['scope'],windows=len(frame),logical_rows=len(links),scope_sha256=sha(path.read_bytes())))
    assert logical==458133 and candidates==195435 and windows==4739
    assert all_finite==complete['complete_diagnostic_windows']
    result=dict(schema='etfe-option-feature-independent-audit-v1',plan_sha256=plan['sha256'],
        auditor_sha256=sha(Path(__file__).read_bytes()),complete_sha256=sha((root/'COMPLETE.json').read_bytes()),
        fields=NAMES,scopes=samples,logical_rows=logical,candidate_links=candidates,physical_windows=windows,
        complete_diagnostic_windows=all_finite,physical_missing_reasons={n:dict(c) for n,c in physical_reasons.items()},
        logical_missing_reasons={n:dict(c) for n,c in logical_reasons.items()},
        all_values_masks_reasons_reconciled=True,all_logical_memberships_reconciled=True,
        rtol=1e-12,atol=1e-12,model_feature_admitted=False,full_feature_schema_complete=False,ready_for_training=False)
    save(root/'INDEPENDENT_AUDIT.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    a=p.parse_args();print(json.dumps(audit(a.root),indent=2))
