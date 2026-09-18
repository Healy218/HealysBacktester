"""Census of remaining cash work over the complete original-record partition."""
from collections import Counter, defaultdict

from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.storage import identity


def pay_date(row):
    return row['record'].get('pay_date' if row['provider'] == 'massive' else 'payable_date')


def dividend_census(candidates, actions, other, renames, cash_events, pending):
    """Count event groups, not duplicate provider rows or overlapping work lists.

    This is an audit, never an admission or an exclusion. A price adjustment and
    a funded-stock entitlement are separate completion requirements.
    """
    originals = {}
    for row in candidates:
        key = record_key(row)
        if key in originals or identity(row['record']) != row['record_sha256']:
            raise ValueError('Unique unchanged original records required')
        originals[key] = row
    consumed = set()
    for treatment in [*actions, *other, *renames]:
        if not treatment.get('replaces'):
            raise ValueError('Explicit original references required')
        for ref in treatment['replaces']:
            key = record_key(ref)
            if (key in consumed or key not in originals
                    or ref['record_sha256'] != originals[key]['record_sha256']):
                raise ValueError('Overlapping or changed resolved record')
            consumed.add(key)
    remaining = {}
    for row in pending:
        key = record_key(row)
        if (key in remaining or key in consumed or key not in originals
                or {k: row[k] for k in originals[key]} != originals[key]):
            raise ValueError('Invalid unresolved record partition')
        remaining[key] = row
    if consumed | remaining.keys() != originals.keys():
        raise ValueError('Every original record must have exactly one treatment')

    cash_actions = {e['action']['event_id']: e for e in actions if e['category'] == 'cash'}
    if len(cash_actions) != sum(e['category'] == 'cash' for e in actions):
        raise ValueError('Duplicate compiled cash event')
    held = {}
    for event in cash_events:
        event_id = event['compiled_event_id']
        if event_id in held or event_id not in cash_actions:
            raise ValueError('Held cash events must be a unique subset of price cash events')
        if event['security_id'] != cash_actions[event_id]['security_id']:
            raise ValueError('Held cash identity differs from price event')
        held[event_id] = event

    groups = defaultdict(list)
    for row in remaining.values():
        if row['category'] == 'cash':
            groups[row['subject_symbol'], row['effective_date']].append(row)
    reviews = []
    for (symbol, day), rows in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1] or '')):
        reviews.append(dict(symbol=symbol, effective_date=day,
            stage='cash_action_uncompiled',
            reasons=sorted({r.get('compilation_reason', 'unreviewed') for r in rows}),
            unit_issues=sorted({issue for r in rows for issue in r['term_issues']}),
            records=[dict(provider=r['provider'], kind=r['kind'], action_id=r['action_id'],
                record_sha256=r['record_sha256'], term=r['term'],
                currency=r['record'].get('currency'), foreign=r['record'].get('foreign'),
                record_date=r['record'].get('record_date'), pay_date=pay_date(r),
                declaration_date=r['record'].get('declaration_date')) for r in sorted(rows, key=record_key)]))
    missing_held = []
    for event_id, event in sorted(cash_actions.items()):
        if event_id in held:
            continue
        day = event.get('effective_date') or event['action']['effective_at'][:10]
        if (event['symbol'], day) in groups:
            raise ValueError('A cash date is partly compiled and partly unresolved')
        rows = [originals[record_key(r)] for r in event['replaces']]
        missing_held.append(dict(event_id=event_id, symbol=event['symbol'], effective_date=day,
            security_id=event['security_id'], stage='held_cash_uncompiled',
            cash_amount=event['cash_amount'],
            record_dates=sorted({str(r['record'].get('record_date')) for r in rows}),
            pay_dates=sorted({str(pay_date(r)) for r in rows}),
            replaces=event['replaces']))
    report = dict(schema='v7-dividend-closure-census-v1', original_provider_records=len(originals),
        resolved_provider_records=len(consumed), pending_provider_records=len(remaining),
        compiled_cash_actions=len(cash_actions), compiled_held_cash_events=len(held),
        uncompiled_cash_groups=len(reviews), compiled_cash_without_held_treatment=len(missing_held),
        remaining_dividend_review_items=len(reviews) + len(missing_held),
        uncompiled_groups_by_reason=dict(sorted(Counter(
            reason for group in reviews for reason in group['reasons']).items())),
        dividends_complete=False, step_1_complete=False, research_ready=False,
        limitations=['Counts do not establish settlement-calendar coverage or executable held treatment',
                     'Complex non-cash distributions and security lifecycle cases remain separate',
                     'No unresolved group is omitted, summed, deduplicated or admitted by this audit'])
    return report, reviews, missing_held
