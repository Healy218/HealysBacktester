"""Bounded precision and acquirer-role reviews; originals remain in the census."""
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.dividend_resolution import compile_dividend_resolutions
from nn_meta.v7.storage import identity


def validate_precision(review, originals):
    """Keep provider precision only when a retained primary amount corroborates it."""
    p = review['precision_review']
    if (review.get('amount_basis') != 'primary_corroborated_provider_precision'
            or p.get('rounding') not in ('nearest', 'truncate')
            or not p.get('rationale') or len(review['payments']) != 1):
        raise ValueError('Explicit single-payment precision review required')
    evidence = {identity(e) for e in review['evidence']}
    if p.get('primary_evidence_identity') not in evidence:
        raise ValueError('Retained primary precision source required')
    quantum = Decimal(p['published_quantum'])
    published = Decimal(p['published_amount'])
    amount = Decimal(review['cash_per_share'])
    if (not all(x.is_finite() and x > 0 for x in (quantum, published, amount))
            or quantum > Decimal('.001') or quantum != Decimal(1).scaleb(quantum.adjusted())):
        raise ValueError('Bounded decimal publication precision required')
    rounding = ROUND_HALF_UP if p['rounding'] == 'nearest' else ROUND_DOWN
    if amount.quantize(quantum, rounding=rounding) != published:
        raise ValueError('Provider amount contradicts published primary amount')
    by_key = {record_key(r): r for r in originals}
    rows = [by_key[record_key(ref)] for ref in review['replaces']]
    for row, ref in zip(rows, review['replaces'], strict=True):
        if (row['record_sha256'] != ref['record_sha256']
                or identity(row['record']) != row['record_sha256']
                or row['subject_symbol'] != review['symbol'] or row['category'] != 'cash'):
            raise ValueError('Unchanged cash records required')
        raw = row['record']
        if ((row['provider'] == 'massive' and raw.get('currency') != 'USD')
                or (row['provider'] == 'alpaca' and raw.get('foreign') is not False)):
            raise ValueError('Precision cannot resolve foreign currency or cash units')
    values = [Decimal(str(r['term'])) for r in rows]
    if not values or amount not in values or min(v.as_tuple().exponent for v in values) != amount.as_tuple().exponent:
        raise ValueError('Retain an original amount with greatest reported precision')
    if any(amount.quantize(Decimal(1).scaleb(v.as_tuple().exponent), rounding=ROUND_HALF_UP) != v for v in values):
        raise ValueError('Original provider amounts contradict at reported precision')
    return True


def acquirer_cash_view(originals, reviews):
    """Exclude only reviewed acquirer roles from the cash compiler's joint-action veto.

    This is NOT a lifecycle disposition. The caller retains full originals and
    unresolved merger records in its census and coverage.
    """
    excluded = set()
    by_key = {record_key(r): r for r in originals}
    for review in reviews:
        for joint in review.get('acquirer_role_reviews', []):
            ref = joint['record']; row = by_key.get(record_key(ref))
            if (row is None or row['record_sha256'] != ref['record_sha256']
                    or identity(row['record']) != row['record_sha256']):
                raise ValueError('Exact original merger record required')
            raw = row['record']; symbol = review['symbol']
            if (row['category'] != 'complex' or row['kind'] not in ('cash_mergers', 'stock_mergers')
                    or row['effective_date'] != review['ex_date']
                    or row['scoped_symbols'] != [symbol] or raw.get('acquirer_symbol') != symbol
                    or raw.get('acquiree_symbol') != joint.get('acquiree_symbol')
                    or raw.get('acquiree_symbol') == symbol
                    or not raw.get('acquirer_cusip') or raw['acquirer_cusip'] != joint.get('acquirer_cusip')
                    or raw.get('acquiree_cusip') != joint.get('acquiree_cusip')
                    or not joint.get('rationale') or joint.get('existing_acquirer_shares_unchanged') is not True
                    or joint.get('consume_merger_record') is not False
                    or joint.get('primary_evidence_identity') not in {identity(e) for e in review['evidence']}):
                raise ValueError('Exclusive unchanged acquirer role and primary terms required')
            excluded.add(record_key(row))
    return [r for r in originals if record_key(r) not in excluded]


def compile_extended_resolutions(originals, reviews, history, calendar, policy, proposal):
    for review in reviews:
        if 'precision_review' in review:
            validate_precision(review, originals)
        elif review.get('amount_basis') != 'exact_primary_terms':
            raise ValueError('Unsupported dividend amount basis')
    view = acquirer_cash_view(originals, reviews)
    actions, leaves, _ = compile_dividend_resolutions(view, reviews, history, calendar, policy, proposal)
    used = {record_key(r) for a in actions for r in a['replaces']}
    return actions, leaves, [r for r in originals if record_key(r) not in used]
