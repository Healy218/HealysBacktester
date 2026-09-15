"""Predeclared expanding V7 folds; labels are purged by complete roll horizons."""
from __future__ import annotations
import pandas as pd


def evaluation_plan():
    return {'schema':'v7-purged-fold-policy-v1','history_start':'2022-03-07',
            'history_end':'2026-09-14','embargo_sessions':10,
            'folds':[{'name':'2024h2','train_end':'2024-06-30','validation_start':'2024-07-01','validation_end':'2024-12-31'},
                     {'name':'2025h1','train_end':'2024-12-31','validation_start':'2025-01-01','validation_end':'2025-06-30'},
                     {'name':'2025h2','train_end':'2025-06-30','validation_start':'2025-07-01','validation_end':'2025-12-31'}],
            'final_test':['2026-01-01','2026-09-14'],
            'evaluation_status':'previously inspected periods; revalidation, not untouched holdout',
            'proposal_policy':'all registered variants; no global winner selection',
            'normalization':'fit only on retained training rows in each fold',
            'label_horizon':'latest exit/roll/mark availability; unresolved positions cannot be scored',
            'baseline':'same eligible proposals, quotes, five shared slots, 10% equity fraction, costs and ledger',
            'search_accounting':'retain every strategy/parameter/timeframe/model/threshold trial',
            'requires_complete_data_and_execution_gate':True}


def fold_masks(rows,fold,calendar,*,embargo_sessions=10,history_start='2022-03-07'):
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
