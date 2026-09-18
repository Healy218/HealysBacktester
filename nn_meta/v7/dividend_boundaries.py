"""Exact dated dividend boundary inputs without changing trading eligibility."""
import numpy as np
import pandas as pd
from nn_meta.v7.storage import identity
from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.dividend_review_extensions import compile_extended_resolutions


def observed_day(raw, calendar, symbol, day):
    if (not isinstance(raw.timestamp.dtype,pd.DatetimeTZDtype) or raw.timestamp.isna().any()
            or raw.timestamp.duplicated().any() or not raw.timestamp.is_monotonic_increasing
            or (pd.DatetimeIndex(raw.timestamp).asi8 % 60_000_000_000).any()):
        raise ValueError('Unique ordered aware minute observations required')
    opening,closing=[v.tz_localize('UTC') for v in calendar.bounds(day)]
    frame=raw[raw.timestamp.ge(opening)&raw.timestamp.lt(closing)]
    values=frame[['Open','High','Low','Close','Volume']]
    if (frame.empty or len(frame)>(closing-opening).total_seconds()/60
            or not np.isfinite(values.to_numpy()).all() or (values.iloc[:,:4]<=0).any().any()
            or (values.Volume<0).any() or (values.High<values[['Open','Low','Close']].max(axis=1)).any()
            or (values.Low>values[['Open','High','Close']].min(axis=1)).any()):
        raise ValueError('Observed valid raw regular-session prices required')
    return dict(stock_ticker=symbol,source_date=day,session_open_ns=opening.value,available_ns=closing.value,
        observed_minutes=len(frame),first_observed_ns=int(frame.timestamp.iloc[0].value),
        last_observed_ns=int(frame.timestamp.iloc[-1].value),raw_open=float(frame.Open.iloc[0]),
        raw_high=float(frame.High.max()),raw_low=float(frame.Low.min()),raw_close=float(frame.Close.iloc[-1]),
        raw_volume=float(frame.Volume.sum()))


def validate_boundary_identity(request, listings, scoped_ids):
    if len(listings)!=2 or request['prior_date']>=request['ex_date']:
        raise ValueError('Adjacent boundary identity pair required')
    fields=('ticker','cik','type','market','locale','currency_name','primary_exchange','composite_figi','share_class_figi')
    a,b=listings
    if (any(a.get(k)!=b.get(k) for k in fields) or any(r.get('active') is not True for r in listings)
            or a.get('ticker')!=request['source_symbol'] or a.get('market')!='stocks'
            or a.get('locale')!='us' or a.get('currency_name')!='usd'
            or a.get('type') not in ('CS','ETF','ADRC') or not a.get('primary_exchange')):
        raise ValueError('Same exact listed security on both boundary days required')
    sid=request['security_id'];mode=request['mode']
    if mode in ('warmup','same_security_alias'):
        if sid not in scoped_ids or a.get('composite_figi')!=sid or not a.get('share_class_figi'):
            raise ValueError('Exact existing scoped identity required')
    elif mode=='separate_cash_security':
        if sid in scoped_ids or a.get('composite_figi')!=sid or not a.get('share_class_figi'):
            raise ValueError('Distinct retained FIGI required; never join successor to predecessor')
    elif mode=='primary_cusip_cash_security':
        if (sid in scoped_ids or sid!='CUSIP:'+request.get('cusip','') or not request.get('cusip')
                or any(r.get('composite_figi') or r.get('share_class_figi') for r in listings)
                or not a.get('cik') or a['cik']!=request.get('cik') or a['type']!='CS'
                or not request.get('primary_identity_evidence')):
            raise ValueError('Primary CUSIP and dated issuer/class witnesses required for missing FIGI')
    else:
        raise ValueError('Unknown finite dividend boundary mode')
    if request.get('changes_trading_eligibility') is not False or request.get('bridges_reorganization') is not False:
        raise ValueError('Dividend boundary cannot change scope or bridge a reorganization')
    return True


def add_boundary_view(history, rows, request, listings, calendar, *, scoped_ids=None, study_start=None):
    validate_boundary_identity(request,listings,set(history.security_id) if scoped_ids is None else scoped_ids)
    sessions=sorted(calendar.sessions);ex=request['ex_date'];prior=request['prior_date']
    if sessions[sessions.index(ex)-1]!=prior or [r['source_date'] for r in rows]!=[prior,ex]:
        raise ValueError('Exact adjacent observed dividend sessions required')
    if any(r['stock_ticker']!=request['source_symbol'] or r['observed_minutes']<=0 for r in rows):
        raise ValueError('Named observed stock source required')
    sid=request['security_id'];mode=request['mode'];result=history.copy()
    if 'dividend_boundary_only' not in result: result['dividend_boundary_only']=False
    if mode=='warmup':
        if ex!=(history.source_date.min() if study_start is None else study_start) or prior>=ex: raise ValueError('Only one preceding scope warmup session allowed')
        current=history[history.security_id.eq(sid)&history.source_date.eq(ex)]
        if (len(current)!=1 or current.stock_ticker.iloc[0]!=request['source_symbol']
                or pd.isna(current.identity_span.iloc[0])):raise ValueError('Observed first scope identity required')
        for k in ('raw_open','raw_high','raw_low','raw_close','raw_volume','observed_minutes','session_open_ns','available_ns'):
            if current[k].iloc[0]!=rows[1][k]:raise ValueError('Warmup anchor differs from existing raw fact')
        span=current.identity_span.iloc[0];rows=rows[:1];listings=listings[:1]
    else:
        span=identity(dict(security_id=sid,start=prior))
    additions=[]
    for raw,listing in zip(rows,listings,strict=True):
        hit=result.security_id.eq(sid)&result.source_date.eq(raw['source_date'])
        if hit.any():
            if mode!='same_security_alias' or not result.loc[hit,'source_status'].eq('no_listed_source').all():
                raise ValueError('Never replace a selected history source')
            result=result.loc[~hit].copy()
        additions.append(dict(raw,security_id=sid,identity_span=span,ticker_changed=False,
            identity_evidence_identity=identity(listing),listed_source_candidates=1,source_status='observed',
            source_selection_evidence=None,provider_composite_figi=listing.get('composite_figi'),
            identity_resolution='reviewed_dividend_boundary_only',identity_resolution_evidence=identity(request),
            resolved_share_class_figi=listing.get('share_class_figi'),dividend_boundary_only=True))
    return pd.concat([result,pd.DataFrame(additions)],ignore_index=True).sort_values(['security_id','source_date']).reset_index(drop=True)


def compile_boundary_dividends(originals,reviews,history,calendar,policy,proposal):
    # A reviewed provider alias is routing metadata. Retain untouched provider
    # payload bytes and references; the caller reconciles against originals.
    view=[dict(r) for r in originals]
    for review in reviews:
        route=review.get('original_symbol_alias')
        if route is None: continue
        if (route!='ELV' or review['symbol']!='ANTM' or review['ex_date']!='2022-06-09'
                or review['security_id']!='BBG000BCG930' or not review.get('alias_identity_evidence')):
            raise ValueError('Finite dated same-security alias review required')
        keys={record_key(r) for r in review['replaces']}
        for row in view:
            if record_key(row) in keys:
                if row['subject_symbol']!=route:raise ValueError('Original alias differs')
                row['subject_symbol']=review['symbol']
    added,leaves,_=compile_extended_resolutions(view,reviews,history,calendar,policy,proposal)
    used={record_key(r) for a in added for r in a['replaces']}
    return added,leaves,[r for r in originals if record_key(r) not in used]
