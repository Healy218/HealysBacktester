"""Finite corrections for records that must not create another cash entitlement.

Original records remain immutable. A correction is a separately hashed review,
not deletion or a blanket inference from a missing provider observation.
"""
from collections import defaultdict
from decimal import Decimal

from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.storage import identity


def reviewed_dispositions(originals, pending, reviews, actions, cash, renames):
    by_key = {record_key(r): r for r in originals}
    if len(by_key) != len(originals) or any(identity(r['record']) != r['record_sha256'] for r in originals):
        raise ValueError('Unique unchanged original records required')
    pending_keys = {record_key(r) for r in pending}
    groups = defaultdict(set)
    for r in originals:
        if r['category'] == 'cash':
            groups[r['subject_symbol'], r['effective_date']].add(record_key(r))
    events = {e['action']['event_id']: e for e in actions}
    used, result = set(), []
    for review in reviews:
        refs = review['replaces']; keys = {record_key(r) for r in refs}
        evidence = review.get('evidence', [])
        if (review.get('schema') != 'v7-dividend-disposition-review-v1'
                or not review.get('rationale') or not evidence
                or identity(evidence) != review.get('evidence_identity')
                or review.get('creates_cash') is not False
                or review.get('creates_price_factor') is not False
                or not keys or len(keys) != len(refs) or used & keys
                or not keys <= pending_keys):
            raise ValueError('Finite source-bound non-cash disposition required')
        for ref in refs:
            if ref['record_sha256'] != by_key[record_key(ref)]['record_sha256']:
                raise ValueError('Disposition original reference changed')
        symbol, day = review['symbol'], review['effective_date']
        if keys != groups.get((symbol, day)):
            raise ValueError('Disposition must retain an entire original cash group')
        rows = [by_key[k] for k in keys]
        kind = review['disposition']
        facts = review['reviewed_facts']
        if kind == 'duplicate_ticker_alias':
            target = events.get(facts.get('target_event_id'))
            if (target is None or target['category'] != 'cash'
                    or target['effective_date'] != day
                    or target['security_id'] != facts.get('security_id')
                    or target['symbol'] == symbol
                    or not any(r['old_symbol'] == symbol and r['new_symbol'] == target['symbol']
                        and r['security_id'] == target['security_id'] and r['effective_date'] <= day
                        for r in renames)):
                raise ValueError('Alias requires the existing dated same-share rename and cash event')
            leaves = [e for e in cash if e['compiled_event_id'] == facts['target_event_id']]
            if len(leaves) != 1:
                raise ValueError('Alias requires one unambiguous existing cash payment')
            for row in rows:
                pay = row['record'].get('pay_date', row['record'].get('payable_date'))
                if (Decimal(row['term']) != Decimal(leaves[0]['cash_per_share'])
                        or row['record']['record_date'] != leaves[0]['record_date']
                        or pay != leaves[0]['pay_date']):
                    raise ValueError('Alias payment terms differ')
        elif kind == 'cancelled_before_record_date':
            if (not facts.get('cancellation_evidence_identity')
                    or facts['cancellation_evidence_identity'] not in {identity(e) for e in evidence}
                    or facts.get('cash_entitlement_survives') is not False
                    or not all(facts['cancellation_date'] < r['record']['record_date'] for r in rows)):
                raise ValueError('Cancellation must precede every original record date')
        elif kind == 'erroneous_cash_record':
            if (facts.get('issuer_common_cash_denied') is not True
                    or facts.get('actual_distribution_symbol') == symbol
                    or not facts.get('actual_distribution_symbol')
                    or len(evidence) < 2):
                raise ValueError('Contrary issuer terms and identified other distribution required')
        elif kind == 'unrelated_record_security':
            cusips = {r['record'].get('cusip') for r in rows if r['provider'] == 'alpaca'}
            if (not cusips or None in cusips or cusips != {facts.get('record_cusip')}
                    or not facts.get('record_issuer') or not facts.get('scoped_issuer')
                    or facts['record_issuer'] == facts['scoped_issuer']
                    or facts.get('successor_relationship') is not False):
                raise ValueError('Positive unrelated CUSIP/issuer mapping required')
        elif kind == 'noncash_distribution':
            related = facts.get('pending_noncash_references', [])
            if (not related or facts.get('cash_per_share') != '0'
                    or not facts.get('share_entitlement')
                    or not all(record_key(r) in pending_keys and record_key(r) not in keys
                        and by_key[record_key(r)]['category'] != 'cash'
                        and r['record_sha256'] == by_key[record_key(r)]['record_sha256'] for r in related)):
                raise ValueError('Noncash correction must retain unresolved share-action dependencies')
        else:
            raise ValueError('Unsupported dividend disposition')
        used.update(keys)
        result.append(dict(schema='v7-reviewed-dividend-disposition-v1', symbol=symbol,
            effective_date=day, replaces=refs, disposition=kind,
            review_identity=identity(review), review=review,
            creates_cash=False, creates_price_factor=False,
            lifecycle_resolved=kind != 'noncash_distribution'))
    return result, [r for r in pending if record_key(r) not in used]


def coverage_with_dispositions(history, originals, actions, pending, dispositions, *, policy, other, renames, cash):
    """Consume corrections while retaining the full original partition and blockers."""
    from nn_meta.v7.action_coverage import coverage_panel
    from nn_meta.v7.dividend_closure import dividend_census
    combined_pending = pending + [r for r in originals if any(
        record_key(r) == record_key(ref) for d in dispositions for ref in d['replaces'])]
    verified, remainder = reviewed_dispositions(originals, combined_pending,
        [d['review'] for d in dispositions], actions, cash, renames)
    if verified != dispositions or {record_key(r) for r in remainder} != {record_key(r) for r in pending}:
        raise ValueError('Disposition treatment changed')
    grouped = {e['compiled_event_id']: e for e in cash}
    dividend_census(originals, actions, [*other, *dispositions], renames, list(grouped.values()), pending)
    resolved = {record_key(r) for d in dispositions for r in d['replaces']}
    panel = coverage_panel(history, [r for r in originals if record_key(r) not in resolved],
        actions, pending, policy=policy, other_instruments=other, renames=renames)
    # A stock distribution is not a harmless no-event: its original effective
    # date remains blocked as well as the retained split/merger dates.
    for d in dispositions:
        if d['disposition'] == 'noncash_distribution':
            affected = panel.stock_ticker.eq(d['symbol']) & panel.source_date.eq(d['effective_date'])
            panel.loc[affected, 'history_admitted'] = False
            panel.loc[affected, 'coverage_status'] = 'unresolved_noncash_distribution'
    panel.attrs['dividend_dispositions_identity'] = identity(dispositions)
    return panel
