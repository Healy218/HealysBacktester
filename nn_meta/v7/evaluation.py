"""Predeclared expanding V7 folds; labels are purged by complete roll horizons."""
from __future__ import annotations
import pandas as pd
from nn_meta.v7.scope import HISTORY_START


def evaluation_plan():
    import json
    from pathlib import Path
    from nn_meta.v7.scope import EVALUATION_FILE
    return json.loads((Path(__file__).resolve().parents[2] / 'docs/specs' / EVALUATION_FILE).read_text())['evaluation']


def fold_masks(rows,fold,calendar,*,embargo_sessions=10,history_start=HISTORY_START):
    required={'decision_at','label_end','label_complete'}
    if not required.issubset(rows):raise ValueError('Complete label horizon fields required')
    if not pd.api.types.is_bool_dtype(rows.label_complete) or rows.label_complete.isna().any():
        raise ValueError('Label completeness must be explicit boolean')
    for column in ('decision_at','label_end'):
        if any(pd.Timestamp(v).tzinfo is None for v in rows[column].dropna()):
            raise ValueError('Label timestamps must have explicit timezones')
    if fold['train_end'] >= fold['validation_start'] or fold['validation_start'] > fold['validation_end']:
        raise ValueError('Fold dates must be chronological and disjoint')
    entry=pd.to_datetime(rows.decision_at,utc=True);end=pd.to_datetime(rows.label_end,utc=True)
    if entry.isna().any() or ((end<entry)&rows.label_complete).any():raise ValueError('Invalid label chronology')
    valid_start=pd.Timestamp(fold['validation_start'],tz='America/New_York').tz_convert('UTC')
    valid_end=(pd.Timestamp(fold['validation_end'],tz='America/New_York')+pd.DateOffset(days=1)).tz_convert('UTC')
    days=sorted(d for d in calendar.sessions if d<fold['validation_start'])
    if type(embargo_sessions) is not int or embargo_sessions<0 or len(days)<embargo_sessions:
        raise ValueError('Insufficient declared embargo calendar')
    purge_boundary=valid_start if embargo_sessions==0 else calendar.bounds(days[-embargo_sessions])[0].tz_localize('UTC')
    train_end=(pd.Timestamp(fold['train_end'],tz='America/New_York')+pd.DateOffset(days=1)).tz_convert('UTC')
    history_start=pd.Timestamp(history_start,tz='America/New_York').tz_convert('UTC')
    train=(entry>=history_start)&(entry<min(train_end,valid_start))&(end<purge_boundary)&rows.label_complete&end.notna()
    validation=(entry>=valid_start)&(entry<valid_end)&(end<valid_end)&rows.label_complete&end.notna()
    return train,validation
