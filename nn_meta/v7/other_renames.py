"""Finite relevance reviews for name changes of unrelated reused tickers."""
from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.daily_identities import EXCHANGES
from nn_meta.v7.storage import identity


def unrelated_renames(unresolved, reviews, listings, history, calendar):
    originals={record_key(r):r for r in unresolved}
    if len(originals)!=len(unresolved):raise ValueError('Unique original records required')
    scoped=set(history.security_id);sessions=sorted(calendar.sessions)
    selected=set(zip(history.stock_ticker,history.source_date))
    treatments=[];consumed=set()
    for review in reviews:
        ref=review['record'];key=record_key(ref);row=originals.get(key)
        if (row is None or key in consumed or key[:2]!=('alpaca','name_changes')
                or row['record_sha256']!=identity(row['record'])
                or ref['record_sha256']!=row['record_sha256']
                or review.get('relationship')!='unrelated_ticker_reuse'
                or not review.get('evidence_identity') or not review.get('rationale')):
            raise ValueError('Exact primary-reviewed unrelated name-change record required')
        day=review['effective_date'];raw=row['record']
        if day not in sessions or sessions.index(day)==0:
            raise ValueError('Exact adjacent exchange sessions required')
        prior=sessions[sessions.index(day)-1]
        before=listings.get((raw['old_symbol'],prior));after=listings.get((raw['new_symbol'],day))
        witness=review['scoped_witness'];anchor=listings.get((witness['symbol'],witness['date']))
        if not before or not after or not anchor:
            raise ValueError('Positive original listings for both legs and scoped witness required')
        for listing in (before,after,anchor):
            if (not listing.get('composite_figi') or not listing.get('share_class_figi')
                    or listing.get('active') is not True or listing.get('market')!='stocks'
                    or listing.get('locale')!='us' or listing.get('primary_exchange') not in EXCHANGES):
                raise ValueError('Positive listed share identity required')
        if (before['ticker']!=raw['old_symbol'] or after['ticker']!=raw['new_symbol']
                or before['composite_figi']!=after['composite_figi']
                or before['share_class_figi']!=after['share_class_figi']
                or before.get('type')!=after.get('type')
                or after['composite_figi'] in scoped
                or anchor['composite_figi'] not in scoped
                or anchor['composite_figi']!=witness['security_id']
                or anchor['share_class_figi']==after['share_class_figi']
                or witness['symbol'] not in row['scoped_symbols']
                or (raw['old_symbol'],prior) in selected or (raw['new_symbol'],day) in selected):
            raise ValueError('Unrelated records cannot remove a scoped identity or successor')
        selected_anchor=history[history.security_id.eq(witness['security_id']) & history.source_date.eq(witness['date'])]
        if (len(selected_anchor)!=1 or selected_anchor.stock_ticker.iloc[0]!=witness['symbol']
                or identity(before)!=review['prior_listing_sha256']
                or identity(after)!=review['effective_listing_sha256']
                or identity(anchor)!=witness['record_sha256']):
            raise ValueError('Changed original identity witness')
        consumed.add(key)
        treatments.append(dict(treatment='reviewed_unrelated_instrument',category='name_change',
            symbol=witness['symbol'],effective_date=day,replaces=[ref],
            other_security_id=after['composite_figi'],other_share_class_figi=after['share_class_figi'],
            review_identity=identity(review),listed_record_sha256=identity(after),
            evidence_identity=review['evidence_identity'],rationale=review['rationale']))
    return treatments,[r for r in unresolved if record_key(r) not in consumed]
