"""Independent natural-key audit of every joined diagnostic cell and row."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from nn_meta.etfe.acquisition import sha,save
from nn_meta.etfe.joined_pilot import verify,load_scope,chunk_name


def audit(root):
    root=Path(root).resolve();plan=verify(root);complete=json.load(open(root/'COMPLETE.json'))
    assert complete['complete'] and complete['plan_sha256']==plan['sha256']
    names=[f['name'] for f in json.load(open(ROOT/'docs/specs/ETFE_FEATURE_MAP_20261003.json'))['fields']]
    order=names+['missing__'+n for n in names]
    assert plan['feature_schema']['matrix_columns']==order and len(names)==221
    assert set(complete['chunk_receipts'])=={chunk_name(c) for c in plan['chunks']}
    seen=set();missing_total=np.zeros(221,dtype='int64');rows_total=0;scope_reports=[];counts={}
    for scope in plan['scopes']:
        data=load_scope(plan,scope);events=data['events'];source_signal=data['signals'];source_tv=data['tv']
        sig=source_signal.set_index(['variant_id','direction','signal_at_ns']);tv=source_tv.set_index('signal_at_ns')
        opt=data['windows'].reset_index().set_index(['symbol','signal_at_ns','minutes']);daily=data['daily'];static=data['static'];technical=data['technical']
        for frame in (sig,tv,opt,daily,static,technical):assert frame.index.is_unique
        offset=0;scoped_missing=np.zeros(221,dtype='int64')
        for chunk in [c for c in plan['chunks'] if c['ticker']==scope['ticker'] and c['minutes']==scope['minutes']]:
            assert chunk['start']==offset and 0<chunk['stop']-chunk['start']<=5000
            path=root/'chunks'/chunk_name(chunk);assert sha(path.read_bytes())==complete['chunk_receipts'][path.name]
            r=json.load(open(path));assert r['chunk']==chunk and r['plan_sha256']==plan['sha256']
            assert r['feature_schema_sha256']==plan['feature_schema_sha256'] and set(r['files'])=={'matrix','reasons','availability','rows'}
            out={}
            for kind,f in r['files'].items():
                p=root/f['path'];assert sha(p.read_bytes())==f['sha256'];out[kind]=pd.read_parquet(p)
            matrix=out['matrix'];reason=out['reasons'];availability=out['availability'];rows=out['rows']
            e=events.iloc[chunk['start']:chunk['stop']].reset_index(drop=True);nrows=len(e)
            assert all(len(f)==nrows for f in out.values()) and r['rows']==nrows
            assert matrix.columns.tolist()==order and reason.columns.tolist()==availability.columns.tolist()==names
            assert all(str(t)=='float64' for t in matrix.iloc[:,:221].dtypes)
            assert all(str(t)=='uint8' for t in matrix.iloc[:,221:].dtypes)
            assert all(str(t)=='int64' for t in availability.dtypes)
            for col in events:pd.testing.assert_series_equal(rows[col],e[col],check_exact=True)
            assert rows.event_ordinal.tolist()==list(range(chunk['start'],chunk['stop']))
            assert rows.source_event_sha256.eq(scope['parents']['causal']['files'][1]['sha256']).all()
            assert not rows.entry_eligible.any() and not rows.model_feature_admitted.any() and rows.selected_contract.isna().all() and rows.actual_dte.isna().all()
            assert np.array_equal(rows.signal_open_ns,e.signal_at_ns-e.minutes.astype('int64')*60_000_000_000)
            expected_ids=[hashlib.sha256(json.dumps(['etfe',x.ticker,x.variant_id,x.direction,int(x.signal_at_ns),int(x.target_dte),None],separators=(',',':'),allow_nan=False).encode()).hexdigest() for x in e.itertuples()]
            assert rows.row_id.tolist()==expected_ids and not seen.intersection(expected_ids) and len(set(expected_ids))==nrows
            seen.update(expected_ids)
            days=pd.to_datetime(e.signal_at_ns,utc=True).dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
            # Independent natural keys, not producer ordinal joins.
            selected={
                'signal':sig.reindex(pd.MultiIndex.from_frame(e[['variant_id','direction','signal_at_ns']])).reset_index(drop=True),
                'tv':tv.reindex(e.signal_at_ns).reset_index(drop=True),
                'technical':technical.reindex(e.signal_at_ns).reset_index(drop=True),
                'static':static.reindex(e.variant_id).reset_index(drop=True),
                'daily':daily.reindex(days).reset_index(drop=True),
                'option':opt.reindex(pd.MultiIndex.from_arrays([e.acquisition_candidate,e.signal_at_ns,e.minutes])).reset_index(drop=True),
                'identity':data['remaining_links'].iloc[chunk['start']:chunk['stop']].reset_index(drop=True)}
            remaining=selected['identity'];olinks=data['option_links'].iloc[chunk['start']:chunk['stop']];tvlinks=data['tv_links'].iloc[chunk['start']:chunk['stop']]
            assert rows.signal_ordinal.tolist()==remaining.signal_ordinal.tolist()
            assert rows.tv_observation_ordinal.tolist()==tvlinks.observation_ordinal.tolist()
            assert rows.context_session_date.tolist()==days.tolist()==remaining.context_session_date.tolist()
            assert rows.option_window_id.tolist()==olinks.window_id.tolist()
            assert selected['option'].window_id.where(e.acquisition_candidate.notna(),None).tolist()==rows.option_window_id.tolist()
            assert source_tv.iloc[rows.tv_observation_ordinal].signal_at_ns.tolist()==e.signal_at_ns.tolist()
            actual_signal=source_signal.iloc[rows.signal_ordinal].reset_index(drop=True)
            for key in ('variant_id','direction','signal_at_ns'):assert actual_signal[key].tolist()==e[key].tolist()
            daily_clock=pd.DatetimeIndex(selected['daily'].available_at).as_unit('ns').asi8
            assert np.array_equal(rows.context_available_at_ns,daily_clock) and (daily_clock<=e.signal_at_ns).all()
            source_clocks=dict(signal=e.signal_at_ns.to_numpy(),tv=e.signal_at_ns.to_numpy(),static=e.signal_at_ns.to_numpy(),identity=e.signal_at_ns.to_numpy(),
                daily=daily_clock,technical=pd.DatetimeIndex(selected['technical'].available_at).as_unit('ns').asi8,option=e.feature_end_ns.to_numpy()+1_000_000_000)
            for i,name in enumerate(names):
                if name in ('ma_gap','px_vs_fast','dir_short','bars_since_signal'):owner='signal'
                elif 'raw__'+name in technical:owner='technical'
                else:
                    owners=[key for key in ('static','daily','tv','identity','option') if 'diagnostic__'+name in selected[key]]
                    assert len(owners)==1,(name,owners);owner=owners[0]
                frame=selected[owner];prefix='raw__' if owner=='technical' else 'diagnostic__'
                expected=frame[prefix+name].to_numpy();missing=pd.isna(expected)
                assert np.array_equal(matrix[name].to_numpy(),expected,equal_nan=True),(scope['ticker'],name,chunk['start'])
                assert np.array_equal(matrix['missing__'+name],missing)
                if owner=='technical':
                    why=np.where(~missing,'observed_raw_unadmitted',np.where(frame.valid,'technical_history_or_denominator_unavailable','incomplete_minute_bin'))
                elif owner=='option':why=frame['reason__'+name].where(e.acquisition_candidate.notna(),'no_prior_date_observed_candidate').to_numpy()
                else:why=frame['reason__'+name].to_numpy()
                assert np.array_equal(reason[name],why),(name,'reason')
                clocks=np.where(missing,-1,source_clocks[owner])
                assert np.array_equal(availability[name],clocks),(name,'availability')
                assert ((clocks==-1)|((clocks>=0)&(clocks<=e.signal_at_ns))).all()
                assert int(missing.sum())==r['missing_by_field'][name]
                scoped_missing[i]+=int(missing.sum())
            assert np.array_equal(rows.missing_fields,matrix.iloc[:,221:].sum(axis=1))
            for value,count in rows.missing_fields.value_counts().items():counts[int(value)]=counts.get(int(value),0)+int(count)
            rows_total+=nrows;offset=chunk['stop']
        assert offset==scope['rows'];missing_total+=scoped_missing
        scope_reports.append(dict(ticker=scope['ticker'],minutes=scope['minutes'],rows=offset))
        print(json.dumps(scope_reports[-1]),flush=True)
    assert rows_total==complete['rows']==len(seen)==458133
    assert dict(zip(names,map(int,missing_total)))==complete['missing_by_field']
    result=dict(schema='etfe-joined-independent-audit-v1',plan_sha256=plan['sha256'],feature_schema_sha256=plan['feature_schema_sha256'],
        complete_sha256=sha((root/'COMPLETE.json').read_bytes()),auditor_sha256=sha(Path(__file__).read_bytes()),
        rows=rows_total,value_fields=221,mask_fields=221,value_cells=rows_total*221,missing_cells=int(missing_total.sum()),
        finite_cells=int(rows_total*221-missing_total.sum()),missing_fields_per_row={str(k):v for k,v in sorted(counts.items())},
        scopes=scope_reports,all_values_masks_reasons_availability_exact=True,all_logical_rows_and_lineage_reconciled=True,
        parent_numerical_components_recomputed=False,model_feature_admitted=False,ready_for_training=False)
    save(root/'INDEPENDENT_AUDIT.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    print(json.dumps(audit(p.parse_args().root),indent=2))
