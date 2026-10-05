"""Canonical diagnostic feature join; no imputation or model admission."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from nn_meta.etfe.acquisition import digest

ROOT=Path(__file__).resolve().parents[2]
MINUTE=60_000_000_000


def schema():
    registry=json.loads((ROOT/'docs/specs/ETFE_FEATURE_MAP_20261003.json').read_text())
    names=[f['name'] for f in registry['fields']]
    groups=dict(technical=names[2:15],daily=names[15:25],signal=names[:2]+[names[25],names[28]],
        identity=names[26:28]+names[49:58],static=names[29:49]+names[164:],tv=names[58:154],option=names[154:164])
    union=[n for fields in groups.values() for n in fields]
    if len(union)!=221 or len(set(union))!=221 or set(union)!=set(names):raise ValueError('Field ownership drift')
    order=names+['missing__'+n for n in names]
    if len(names)!=221 or len(set(names))!=221 or registry['model_order']!=order:raise ValueError('Registered order drift')
    return dict(schema='etfe-joined-diagnostic-v2',fields=names,matrix_columns=order,groups=groups,
        value_dtype='float64',mask_dtype='uint8',availability_dtype='int64_utc_ns_missing_minus_one',
        field_binding_amendment='docs/specs/ETFE_FEATURE_BINDINGS_20261005.json',
        artifact_kind='unadmitted_diagnostics',model_feature_admitted=False,ready_for_training=False)


def require_unique(frame,label):
    if not frame.index.is_unique:raise ValueError(label+': duplicate source key')


def exact_take(frame,keys,label):
    require_unique(frame,label)
    if not pd.Index(keys).isin(frame.index).all():raise ValueError(label+': missing source key')
    return frame.loc[list(keys)].reset_index(drop=True)


def source_values(frame,names,prefix='diagnostic__'):
    values=frame[[prefix+n for n in names]].copy();values.columns=names
    masks=frame[['missing__'+prefix+n for n in names]].copy();masks.columns=names
    if any(str(t)!='float64' for t in values.dtypes):raise ValueError('Source value dtype drift')
    if any(str(t)!='uint8' for t in masks.dtypes):raise ValueError('Source mask dtype drift')
    if np.isinf(values.to_numpy()).any() or not np.array_equal(masks.to_numpy(),values.isna().to_numpy()):
        raise ValueError('Source mask/value mismatch')
    return values


def validate_bundle(matrix,reasons,availability,rows,layout=None):
    layout=layout or schema();names=layout['fields']
    if matrix.columns.tolist()!=layout['matrix_columns'] or reasons.columns.tolist()!=names or availability.columns.tolist()!=names:
        raise ValueError('Canonical column order mismatch')
    if any(len(x)!=len(rows) for x in (matrix,reasons,availability)):raise ValueError('Row count mismatch')
    if any(str(t)!='float64' for t in matrix[names].dtypes) or any(str(t)!='uint8' for t in matrix.iloc[:,221:].dtypes):
        raise ValueError('Canonical dtype mismatch')
    if any(str(t)!='int64' for t in availability.dtypes):raise ValueError('Availability dtype mismatch')
    values=matrix[names].to_numpy();missing=np.isnan(values);times=availability.to_numpy()
    if np.isinf(values).any() or not np.array_equal(missing,matrix.iloc[:,221:].to_numpy()):raise ValueError('Invalid values/masks')
    if not np.array_equal(missing,times==-1) or ((~missing)&((times<0)|(times>rows.signal_at_ns.to_numpy()[:,None]))).any():
        raise ValueError('Future/unknown availability')
    if reasons.isna().any().any() or reasons.eq('').any().any():raise ValueError('Missing reason')
    finite_reasons=reasons.isin(['observed_diagnostic','observed_raw_unadmitted','catalog_identity','dated_identity']).to_numpy()
    if not np.array_equal(finite_reasons,~missing):raise ValueError('Reason/missingness mismatch')
    if not rows.row_id.is_unique or rows.model_feature_admitted.any() or rows.entry_eligible.any() or rows.selected_contract.notna().any():
        raise ValueError('Diagnostic identity/admission mismatch')
    if not np.array_equal(rows.missing_fields,missing.sum(axis=1)):raise ValueError('Missing-field census mismatch')


def join_batch(data,start,stop,*,event_sha256,layout=None):
    layout=layout or schema();groups=layout['groups'];events=data['events']
    if not 0<=start<stop<=len(events):raise ValueError('Nonempty ordinal range required')
    e=events.iloc[start:stop].reset_index(drop=True);ordinals=np.arange(start,stop,dtype='int64');at=e.signal_at_ns.to_numpy()
    if len(set(e.minutes))!=1 or len(set(e.ticker))!=1 or not e.minutes.isin([1,5,15]).all():raise ValueError('Mixed/unknown scope')
    if e.entry_eligible.any():raise ValueError('Predecessor unexpectedly admitted entries')
    if not e.direction.isin(['long','short']).all():raise ValueError('Unknown direction')
    if not np.array_equal(e.feature_start_ns,at-(e.minutes.astype('int64')+1)*MINUTE) or not np.array_equal(e.feature_end_ns,at-MINUTE):
        raise ValueError('Event feature boundary mismatch')
    for key in ('remaining_links','tv_links','option_links'):
        source=data[key]
        if len(source)!=len(events) or not np.array_equal(source.event_ordinal,np.arange(len(events))):raise ValueError('Logical ordinal drift: '+key)
        if source.model_feature_admitted.any():raise ValueError('Predecessor admission drift')
    links=data['remaining_links'].iloc[start:stop].reset_index(drop=True)
    tvlinks=data['tv_links'].iloc[start:stop].reset_index(drop=True)
    olinks=data['option_links'].iloc[start:stop].reset_index(drop=True)
    signal=exact_take(data['signals'],links.signal_ordinal,'signal')
    for n in ('variant_id','strategy','direction','signal_at_ns'):
        if signal[n].tolist()!=e[n].tolist():raise ValueError('Signal identity mismatch: '+n)
    if links.variant_id.tolist()!=e.variant_id.tolist():raise ValueError('Variant link mismatch')
    tv=exact_take(data['tv'],tvlinks.observation_ordinal,'TV')
    if not np.array_equal(tv.signal_at_ns,at):raise ValueError('TV clock mismatch')
    stock=exact_take(data['technical'],at,'stock')
    if not np.array_equal(stock.Close,e.raw_spot):raise ValueError('Raw spot mismatch')
    clocks_stock=pd.DatetimeIndex(stock.available_at).as_unit('ns').asi8
    if (clocks_stock<0).any() or (clocks_stock>at).any():raise ValueError('Stock availability exceeds decision')
    days=pd.to_datetime(at,utc=True).tz_convert('America/New_York').strftime('%Y-%m-%d')
    if list(days)!=links.context_session_date.tolist():raise ValueError('Context date mismatch')
    daily=exact_take(data['daily'],days,'daily context')
    clocks_daily=pd.DatetimeIndex(daily.available_at).as_unit('ns').asi8
    if (clocks_daily<0).any() or (clocks_daily>at).any():raise ValueError('Daily context from future')
    static=exact_take(data['static'],e.variant_id,'catalog')
    for strategy in e.strategy.unique():
        if not static.loc[e.strategy.eq(strategy),'diagnostic__strat_'+strategy].eq(1).all():raise ValueError('Catalog family mismatch')
    if not static['diagnostic__timeframe_'+str(int(e.minutes.iloc[0]))].eq(1).all():raise ValueError('Catalog timeframe mismatch')
    if not np.array_equal(signal.diagnostic__dir_short,e.direction.eq('short').astype(float)):raise ValueError('Direction feature mismatch')
    windows=data['windows'];require_unique(windows,'option window')
    present=olinks.window_id.notna().to_numpy()
    if not np.array_equal(present,e.acquisition_candidate.notna()):raise ValueError('Candidate/window null mismatch')
    wids=olinks.loc[present,'window_id']
    selected=exact_take(windows,wids,'option window')
    if len(selected):
        expected=e.loc[present].reset_index(drop=True)
        for n,source in [('symbol','acquisition_candidate'),('signal_at_ns','signal_at_ns'),('minutes','minutes'),
                         ('feature_start_ns','feature_start_ns'),('feature_end_ns','feature_end_ns'),('inside_stock_session','feature_inside_stock_session')]:
            if selected[n].tolist()!=expected[source].tolist():raise ValueError('Option window identity mismatch: '+n)
        if not np.array_equal(selected.feature_start_ns,expected.signal_at_ns-(expected.minutes+1)*MINUTE) or not np.array_equal(selected.feature_end_ns,expected.signal_at_ns-MINUTE):
            raise ValueError('Option feature boundary mismatch')
        if selected.model_feature_admitted.any():raise ValueError('Option admission drift')
    selected.index=np.flatnonzero(present)
    option=selected.reindex(pd.RangeIndex(len(e)))
    values={};reasons={};available={}
    frames=dict(technical=stock,signal=signal,identity=links,static=static,daily=daily,tv=tv)
    for frame in (signal,links,static,daily,tv):
        if frame.model_feature_admitted.any():raise ValueError('Predecessor admission drift')
    clock=dict(technical=clocks_stock,signal=at,identity=at,static=at,daily=clocks_daily,tv=at,
               option=e.feature_end_ns.to_numpy()+1_000_000_000)
    for group,names in groups.items():
        if group=='option':
            if len(selected):source_values(selected,names)
            v=pd.DataFrame({n:option['diagnostic__'+n].astype('float64') for n in names})
            why=pd.DataFrame({n:option['reason__'+n].where(present,'no_prior_date_observed_candidate') for n in names})
        else:
            frame=frames[group];v=source_values(frame,names,prefix='raw__' if group=='technical' else 'diagnostic__')
            if group=='technical':
                why=pd.DataFrame({n:np.where(v[n].notna(),'observed_raw_unadmitted',
                    np.where(stock.valid,'technical_history_or_denominator_unavailable','incomplete_minute_bin')) for n in names})
            else:why=frame[['reason__'+n for n in names]].copy();why.columns=names
        for n in names:
            values[n]=v[n].to_numpy(dtype='float64');reasons[n]=why[n].to_numpy()
            available[n]=np.where(v[n].notna(),clock[group],-1).astype('int64')
    names=layout['fields'];value=pd.DataFrame(values)[names];reason=pd.DataFrame(reasons)[names];availability=pd.DataFrame(available)[names]
    matrix=pd.concat([value,value.isna().astype('uint8').add_prefix('missing__')],axis=1)
    rows=e.copy();rows.insert(0,'event_ordinal',ordinals)
    rows.insert(0,'row_id',[digest(['etfe',r.ticker,r.variant_id,r.direction,int(r.signal_at_ns),int(r.target_dte),None]) for r in e.itertuples()])
    rows['signal_open_ns']=at-e.minutes.to_numpy(dtype='int64')*MINUTE;rows['selected_contract']=None;rows['actual_dte']=np.nan
    rows['source_event_sha256']=event_sha256;rows['signal_ordinal']=links.signal_ordinal
    rows['tv_observation_ordinal']=tvlinks.observation_ordinal;rows['context_session_date']=list(days)
    rows['context_available_at_ns']=clocks_daily;rows['option_window_id']=olinks.window_id
    rows['missing_fields']=value.isna().sum(axis=1).astype('int16');rows['model_feature_admitted']=False
    validate_bundle(matrix,reason,availability,rows,layout)
    return dict(matrix=matrix,reasons=reason,availability=availability,rows=rows)
