"""Explicit user-directed study exclusions; never relabel them as PIT knowledge."""


def exclude_securities(membership, declaration):
    if (declaration.get('schema') != 'v7-user-universe-exclusions-v1'
            or declaration.get('scope') != 'entire_research_history'
            or declaration.get('rerank_or_replace') is not False
            or declaration.get('historically_known_eligibility') is not False):
        raise ValueError('Explicit historical study restriction required')
    exclusions = declaration['exclusions']
    ids = [e['security_id'] for e in exclusions]
    if not ids or len(set(ids)) != len(ids) or any(not v for v in ids):
        raise ValueError('Distinct excluded security identities required')
    for event in exclusions:
        actual = set(membership.loc[membership.security_id.eq(event['security_id']), 'ticker'])
        if actual != set(event['membership_tickers']):
            raise ValueError('Exclusion identity/ticker set differs from captured membership')
    mask = membership.security_id.isin(ids)
    kept, removed = membership.loc[~mask].copy(), membership.loc[mask].copy()
    if kept.empty:
        raise ValueError('Study exclusion removed the entire universe')
    return kept, removed
