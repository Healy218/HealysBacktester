"""Compile exact-session rename routes without changing security identities."""
import pandas as pd

from nn_meta.v7.action_inventory import iso_day
from nn_meta.v7.storage import identity


def compile_routes(aliases, reviews, identities, stock):
    """Extend the existing alias consumer schema with evidence-reviewed routes.

    Publication evidence is verified by the caller. A route chooses between
    exact-day listings of the SAME security; it cannot stitch different FIGIs,
    create membership, invent observations or establish option deliverables.
    """
    keys = ['stock_ticker', 'source_date']
    if identities.duplicated(keys).any() or stock.duplicated(keys).any():
        raise ValueError('Unique exact-day identity and stock inputs required')
    if aliases.duplicated(['security_id', 'date']).any():
        raise ValueError('Existing source routes collide')
    occupied = set(zip(aliases.security_id, aliases.date))
    panel = identities.set_index(keys)
    raw = stock.set_index(keys)
    additions = []
    for review in reviews:
        day = iso_day(review['date'])
        security = review['security_id']
        old, new = review['old_symbol'], review['stock_ticker']
        if (not all(isinstance(s, str) and s for s in (security, old, new))
                or old == new or (security, day) in occupied
                or review.get('kind') != 'same_security_listing_transfer'
                or not review.get('evidence')):
            raise ValueError('Unique evidence-backed same-security rename required')
        for symbol in (old, new):
            if (symbol, day) not in panel.index:
                raise ValueError('Both rename listings must be captured on the exact day')
            row = panel.loc[(symbol, day)]
            if (pd.isna(row.listed_security_id) or row.listed_security_id != security
                    or row.identity_status != 'dated_identity'
                    or not isinstance(row.identity_evidence_identity, str)
                    or not row.identity_evidence_identity):
                raise ValueError('Rename cannot override unknown or different security identities')
        if (new, day) not in raw.index:
            raise ValueError('Selected rename source has no exact-day raw facts')
        observed = raw.loc[(new, day)]
        if pd.isna(observed.observed_minutes) or observed.observed_minutes <= 0:
            raise ValueError('Selected rename source must have actual observations')
        for evidence in review['evidence']:
            available = pd.Timestamp(evidence['publication_available_at'])
            if (pd.isna(available) or available.tzinfo is None
                    or available.value > observed.session_open_ns):
                raise ValueError('Rename publication must be available by the session open')
        occupied.add((security, day))
        additions.append(dict(membership_ticker=old, date=day, stock_ticker=new,
            security_id=security, observed_minutes=int(observed.observed_minutes),
            action_id='reviewed-route:' + identity(review),
            stock_receipt=review['stock_receipt'],
            identity_receipt=review['identity_receipt']))
    return pd.concat([aliases, pd.DataFrame(additions)], ignore_index=True)
