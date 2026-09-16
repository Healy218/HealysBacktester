"""Exact-day listed identities and explicit continuity breaks for raw history."""
from collections import defaultdict
import pandas as pd
from nn_meta.v7.storage import identity


def attach_day(stock, records, *, day, evidence_identity):
    """Never propagate a month-end identity or resolve collisions by row order."""
    if (not evidence_identity or stock.empty or not {'stock_ticker','source_date'}.issubset(stock)
            or not stock.source_date.eq(day).all() or stock.stock_ticker.duplicated().any()):
        raise ValueError('Unique stock symbols on one exact source date required')
    by_symbol=defaultdict(list)
    for record in records:
        # Explicit punctuation normalization is the existing OCC-root convention.
        by_symbol[record['ticker'].replace('.','')].append(record)
    rows=[]
    for symbol in stock.stock_ticker:
        matches=by_symbol.get(symbol.replace('.',''),[])
        security=ticker=exchange=kind=None
        if not matches:status='absent_from_listed_capture'
        elif len(matches)>1:status='ambiguous_listed_symbol'
        else:
            record=matches[0]
            ticker,exchange,kind=record['ticker'],record['primary_exchange'],record.get('type')
            security=record.get('composite_figi') or None
            if security is not None and not isinstance(security,str):
                raise ValueError('Invalid dated security identifier')
            status='dated_identity' if security else 'missing_composite_figi'
        rows.append(dict(stock_ticker=symbol,source_date=day,reference_ticker=ticker,
            listed_security_id=security,primary_exchange=exchange,instrument_type=kind,
            identity_status=status,identity_evidence_identity=evidence_identity))
    return pd.DataFrame(rows)


def continuity_spans(panel, sessions):
    """Break at unknown, changed identity, or missing calendar sessions.

    These are provider-dated identity spans, not proof of complete action history
    or contemporaneous publication vintage. Aliases require separate stitching.
    """
    if sessions!=sorted(set(sessions)) or panel.duplicated(['stock_ticker','source_date']).any():
        raise ValueError('Unique ordered calendar and source symbol/date identities required')
    positions={day:i for i,day in enumerate(sessions)}
    if not panel.source_date.isin(positions).all():raise ValueError('Identity date outside captured calendar')
    result=panel.sort_values(['stock_ticker','source_date']).reset_index(drop=True).copy()
    spans=[];last_symbol=last_security=last_position=current=None
    for row in result.itertuples(index=False):
        position=positions[row.source_date]
        security=None if pd.isna(row.listed_security_id) else row.listed_security_id
        if security is None:
            current=None
        elif (row.stock_ticker!=last_symbol or security!=last_security
              or last_position is None or position!=last_position+1 or current is None):
            current=identity(dict(symbol=row.stock_ticker,security_id=security,start=row.source_date))
        spans.append(current)
        last_symbol,last_security,last_position=row.stock_ticker,security,position
    result['identity_span']=spans
    return result
