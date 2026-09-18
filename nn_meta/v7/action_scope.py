"""Finite reviewed treatment of action records for unrelated reused tickers."""
from collections import defaultdict

from nn_meta.v7.action_inventory import iso_day
from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.daily_identities import EXCHANGES
from nn_meta.v7.storage import identity


def other_instrument_treatments(unresolved, reviews, listings, *, scoped_ids, selected_keys):
    """Resolve whole simple groups only, retaining every original reference.

    Reviewers must establish unrelated instruments, not corporate successors.
    Exact-day positive identities and distinct share classes are mandatory.
    Neither a missing listing nor a new FIGI alone proves irrelevance.
    """
    by_key, groups = {}, defaultdict(list)
    complex_days = set()
    for row in unresolved:
        key = record_key(row)
        if key in by_key or row['record_sha256'] != identity(row['record']):
            raise ValueError('Unique unchanged original records required')
        by_key[key] = row
        if row['category'] == 'complex':
            complex_days.update((s, row['effective_date']) for s in row['scoped_symbols'])
        else:
            groups[row['subject_symbol'], row['effective_date']].append(row)
    consumed, treatments = set(), []
    for review in reviews:
        symbol, day = review['symbol'], iso_day(review['effective_date'])
        key = symbol, day
        listing = listings.get(key)
        refs = review['replaces']
        rkeys = [record_key(r) for r in refs]
        if (review.get('treatment') != 'reviewed_unrelated_instrument'
                or not review.get('rationale') or not refs or len(rkeys) != len(set(rkeys))
                or consumed.intersection(rkeys) or key in selected_keys or key in complex_days
                or set(rkeys) != {record_key(r) for r in groups.get(key, [])}
                or any(by_key[k]['category'] != 'cash' for k in rkeys)):
            raise ValueError('Finite whole cash group for an unrelated instrument required')
        if (not listing or identity(listing) != review['listed_record_sha256']
                or listing.get('ticker') != symbol or listing.get('active') is not True
                or listing.get('market') != 'stocks' or listing.get('locale') != 'us'
                or listing.get('primary_exchange') not in EXCHANGES
                or not listing.get('share_class_figi') or not listing.get('composite_figi')
                or listing['composite_figi'] != review['other_security_id']
                or listing['share_class_figi'] != review['other_share_class_figi']
                or listing['composite_figi'] in scoped_ids
                or review.get('relationship') != 'unrelated_ticker_reuse'
                or review.get('successor_or_entitlement_inference') is not False):
            raise ValueError('Exact positive unrelated listed identity required')
        for ref in refs:
            if ref['record_sha256'] != by_key[record_key(ref)]['record_sha256']:
                raise ValueError('Reviewed original action record changed')
        consumed.update(rkeys)
        treatments.append(dict(symbol=symbol, effective_date=day, replaces=refs,
            treatment=review['treatment'], other_security_id=listing['composite_figi'],
            other_share_class_figi=listing['share_class_figi'], review_identity=identity(review),
            listed_record_sha256=identity(listing), rationale=review['rationale']))
    return treatments, [row for row in unresolved if record_key(row) not in consumed]
