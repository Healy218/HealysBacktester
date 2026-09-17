"""Exact-date identity resolution using retained share-class identifiers.

Original provider composite IDs remain visible. This never propagates an
identity into a day without a captured, unambiguous matching share class.
"""
import pandas as pd

from nn_meta.v7.action_inventory import iso_day
from nn_meta.v7.daily_identities import EXCHANGES
from nn_meta.v7.storage import identity

MATCH_FIELDS = ('ticker', 'share_class_figi', 'primary_exchange', 'type',
                'market', 'locale', 'currency_name', 'cik')


def review_mapping(review, anchor, current, *, scoped_ids):
    """Validate a reviewed prior anchor and exact-day share-class witness.

    Records must be selected uniquely from verified full daily captures by the
    caller. No future record, issuer-name similarity or observed price is used.
    """
    day, prior = iso_day(review['date']), iso_day(review['anchor_date'])
    sid, symbol, share = review['security_id'], review['symbol'], review['share_class_figi']
    if (not prior < day or sid not in scoped_ids
            or not isinstance(share, str) or not share
            or not isinstance(symbol, str) or not symbol
            or review['anchor_record_sha256'] != identity(anchor)
            or review['record_sha256'] != identity(current)):
        raise ValueError('Reviewed exact-day records and a preceding scoped anchor required')
    if (anchor.get('composite_figi') != sid or anchor.get('ticker') != symbol
            or anchor.get('share_class_figi') != share
            or current.get('composite_figi') != review['original_composite_figi']
            or current.get('composite_figi') in scoped_ids
            or any(anchor.get(k) != current.get(k) for k in MATCH_FIELDS)
            or any(not current.get(k) for k in MATCH_FIELDS if k != 'cik')
            or anchor.get('active') is not True or current.get('active') is not True
            or current['primary_exchange'] not in EXCHANGES
            or current['market'] != 'stocks' or current['locale'] != 'us'):
        raise ValueError('Exact matching listed share class required; competing study IDs cannot be merged')
    return dict(stock_ticker=symbol, source_date=day, security_id=sid,
        provider_composite_figi=current.get('composite_figi'), share_class_figi=share,
        anchor_date=prior, identity_resolution='reviewed_exact_day_share_class',
        identity_resolution_evidence=identity(review))


def canonical_candidates(panel, mappings):
    """Make a temporary canonical view for the existing history selector.

    The source panel is unchanged; output histories must retain the returned
    mappings alongside original composite IDs. Only explicitly reviewed keys
    are translated. This adapter supplies a dated *resolved* identity to the
    existing selector rather than pretending the raw composite ID was corrected.
    """
    keys = ['stock_ticker', 'source_date']
    if panel.duplicated(keys).any():
        raise ValueError('Unique captured symbol/session identities required')
    result = panel.copy().set_index(keys)
    seen = set()
    for mapping in mappings:
        key = mapping['stock_ticker'], mapping['source_date']
        if key in seen or key not in result.index:
            raise ValueError('Unique exact captured session resolution required')
        seen.add(key)
        current = result.loc[key, 'listed_security_id']
        expected = mapping['provider_composite_figi']
        if not ((pd.isna(current) and expected is None) or (pd.notna(current) and current == expected)):
            raise ValueError('Resolution differs from the original composite identity')
        if result.loc[key, 'identity_status'] not in ('dated_identity', 'missing_composite_figi'):
            raise ValueError('Cannot resolve an absent or ambiguous listing by share class')
        result.loc[key, 'listed_security_id'] = mapping['security_id']
        result.loc[key, 'identity_status'] = 'dated_identity'
    return result.reset_index()
