"""Select raw history by exact dated security identity across listed renames."""
import numpy as np
import pandas as pd

from nn_meta.v7.storage import identity

RAW_FIELDS=('raw_open','raw_high','raw_low','raw_close','raw_volume')


def security_history(candidates, clock, *, security_id, source_overrides=()):
    """One complete calendar panel; zero or multiple sources remain unknown.

    Candidates must already have the target's exact-date listed identity. Equal
    FIGIs on adjacent days can continue across a ticker rename. A reused ticker
    with a different FIGI cannot enter this panel. This selects raw observations;
    complete action evidence remains a separate requirement for causal features.
    """
    required={'source_date','stock_ticker','listed_security_id','identity_status',
        'identity_evidence_identity','observed_minutes','available_ns','session_open_ns',
        'first_observed_ns','last_observed_ns',*RAW_FIELDS}
    if (not security_id or not required.issubset(candidates)
            or not {'source_date','session_open_ns','stock_available_ns'}.issubset(clock)
            or clock.empty or clock.source_date.tolist()!=sorted(set(clock.source_date))
            or candidates.duplicated(['stock_ticker','source_date']).any()
            or not candidates.listed_security_id.eq(security_id).all()
            or not candidates.identity_status.eq('dated_identity').all()
            or candidates.identity_evidence_identity.isna().any()
            or not candidates.identity_evidence_identity.map(lambda v:isinstance(v,str) and bool(v)).all()
            or not candidates.source_date.isin(clock.source_date).all()):
        raise ValueError('Exact unique source/day candidates for one dated security required')
    indexed=candidates.set_index('source_date')
    expected=clock.set_index('source_date').reindex(indexed.index)
    if (not pd.api.types.is_integer_dtype(indexed.observed_minutes)
            or indexed.observed_minutes.isna().any() or indexed.observed_minutes.lt(0).any()
            or not pd.api.types.is_integer_dtype(indexed.available_ns)
            or not indexed.available_ns.eq(expected.stock_available_ns).all()
            or not indexed.session_open_ns.eq(expected.session_open_ns).all()):
        raise ValueError('Raw source session clocks or observation counts differ')
    observed=indexed.observed_minutes.gt(0)
    values=indexed.loc[observed,list(RAW_FIELDS)].to_numpy(float)
    if (not np.isfinite(values).all() or (values[:,:4]<=0).any() or (values[:,4]<0).any()
            or indexed.loc[~observed,list(RAW_FIELDS)].notna().any().any()):
        raise ValueError('Missing or invalid raw prices disagree with source observations')
    counts=indexed.groupby(level=0).size()
    unique=indexed.loc[~indexed.index.duplicated(keep=False)].copy()
    reviewed_days={}
    for review in source_overrides:
        day=review['source_date']
        if not clock.source_date.iloc[0]<=day<=clock.source_date.iloc[-1]:
            continue
        if (day in reviewed_days or review['security_id']!=security_id
                or not isinstance(review.get('evidence_identity'),str) or not review['evidence_identity']):
            raise ValueError('Unique exact-day alias review for this security required')
        chosen=candidates[candidates.source_date.eq(day) & candidates.stock_ticker.eq(review['stock_ticker'])]
        if len(chosen)!=1 or chosen.observed_minutes.iloc[0]<=0:
            raise ValueError('Reviewed alias must select an observed matching listed source')
        unique=pd.concat([unique.loc[unique.index!=day],chosen.set_index('source_date')])
        reviewed_days[day]=review['evidence_identity']
    # Nullable integers prevent nanosecond timestamps passing through float64.
    for field in ('first_observed_ns','last_observed_ns'):
        unique[field]=unique[field].astype('Int64')
    result=clock[['source_date','session_open_ns','stock_available_ns']].set_index('source_date').copy()
    columns=['stock_ticker','identity_evidence_identity','observed_minutes',
             'first_observed_ns','last_observed_ns',*RAW_FIELDS]
    result=result.join(unique[columns],how='left')
    result['listed_source_candidates']=counts.reindex(result.index,fill_value=0).astype('int64')
    known=pd.Series(result.index.isin(unique.index),index=result.index)
    result['observed_minutes']=result.observed_minutes.fillna(0).astype('int64')
    result['security_id']=security_id
    result['available_ns']=result.pop('stock_available_ns')
    result['source_status']=np.select([result.listed_source_candidates.eq(0),
        ~known & result.listed_source_candidates.gt(1),result.observed_minutes.eq(0)],
        ['no_listed_source','ambiguous_listed_sources','listed_no_stock_observation'],default='observed')
    result['source_selection_evidence']=pd.Series(reviewed_days,dtype='string').reindex(result.index)
    starts=known & ~known.shift(fill_value=False)
    run_ids=pd.Series({day:identity(dict(security_id=security_id,start=day)) for day in result.index[starts]},dtype='string')
    # Only span identifiers propagate through a run of known exact-day identities.
    # Raw prices and observations are never filled.
    result['identity_span']=run_ids.reindex(result.index).ffill().where(known,None)
    result['ticker_changed']=known & known.shift(fill_value=False) & result.stock_ticker.ne(result.stock_ticker.shift())
    for field in ('stock_ticker','identity_evidence_identity','identity_span'):
        result[field]=result[field].astype('string')
    result=result.reset_index()
    result.attrs.update(price_basis='raw Alpaca; exact dated identity selection',research_ready=False)
    return result
