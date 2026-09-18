"""Fill missing source selections with observed, exact-identity supplemental data."""
import pandas as pd

from nn_meta.v7.security_history import security_history


def supplement_history(history, candidates, *, security_id, evidence_identity):
    if (not evidence_identity or security_id not in set(history.security_id)
            or candidates.empty or not candidates.listed_security_id.eq(security_id).all()
            or candidates.source_date.duplicated().any()):
        raise ValueError('Explicit scoped security and unique exact-identity supplement required')
    old = history[history.security_id.eq(security_id)].copy()
    old_index = old.set_index('source_date')
    if (not candidates.source_date.isin(old.source_date).all()
            or not old_index.loc[candidates.source_date, 'source_status'].eq('no_listed_source').all()):
        raise ValueError('Supplement may fill missing selections only, never replace existing facts')
    known = old[old.stock_ticker.notna()].copy()
    known['listed_security_id'] = security_id
    known['identity_status'] = 'dated_identity'
    overrides = [dict(source_date=r.source_date, stock_ticker=r.stock_ticker, security_id=security_id,
        evidence_identity=r.source_selection_evidence) for r in old.itertuples()
        if pd.notna(r.source_selection_evidence)]
    clock = old[['source_date', 'session_open_ns', 'available_ns']].rename(columns={'available_ns':'stock_available_ns'})
    result = security_history(pd.concat([known, candidates], ignore_index=True), clock,
                              security_id=security_id, source_overrides=overrides)
    # Retain all previous resolution provenance; this operation is additive.
    for field in ('provider_composite_figi', 'identity_resolution',
                  'identity_resolution_evidence', 'resolved_share_class_figi'):
        if field not in old:
            raise ValueError('Explicit original identity provenance required')
        result[field] = result.source_date.map(old_index[field]).astype('string')
    added = result.source_date.isin(candidates.source_date)
    # A selected source can have had multiple original listing candidates and
    # an explicit routing review. Rebuilding from selected rows must not erase
    # that ambiguity count (or another unresolved source classification).
    for field in ('listed_source_candidates', 'source_status'):
        result.loc[~added, field] = result.loc[~added, 'source_date'].map(old_index[field])
    result.loc[added, 'provider_composite_figi'] = security_id
    result.loc[added, 'identity_resolution'] = 'supplemented_exact_day_identity'
    result.loc[added, 'identity_resolution_evidence'] = evidence_identity
    if len(result) != len(old):
        raise ValueError('Supplement changed the security calendar grid')
    return pd.concat([history[~history.security_id.eq(security_id)], result], ignore_index=True).sort_values(
        ['security_id', 'source_date']).reset_index(drop=True)
