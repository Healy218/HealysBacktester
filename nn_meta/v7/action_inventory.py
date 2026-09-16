"""Full captured-action reconciliation; never automatic causal-price admission.

Provider records are retrospective. Matching amounts/ratios cannot establish
publication clocks, security identity, cash units or combined-event semantics.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from nn_meta.v7.storage import identity

SYMBOL_FIELDS = frozenset({'symbol', 'ticker', 'old_symbol', 'new_symbol',
    'source_symbol', 'acquiree_symbol', 'acquirer_symbol', 'alternate_symbol'})
SIMPLE = {'cash_dividends': 'cash', 'forward_splits': 'split', 'reverse_splits': 'split'}


def symbols(record):
    """Retain roles, including movement legs; never assign identity by substring."""
    found = []
    def visit(value, prefix=''):
        if isinstance(value, dict):
            for key, child in value.items():
                path = prefix + key
                if key in SYMBOL_FIELDS and isinstance(child, str) and child:
                    found.append({'role': path, 'symbol': child})
                elif isinstance(child, (dict, list)):
                    visit(child, path + '.')
        elif isinstance(value, list):
            for i, child in enumerate(value):
                visit(child, prefix + str(i) + '.')
    visit(record)
    return sorted(found, key=lambda r: (r['role'], r['symbol']))


def iso_day(value):
    if not isinstance(value, str):
        raise ValueError('Exact ISO action date required')
    parsed = date.fromisoformat(value).isoformat()
    if parsed != value:
        raise ValueError('Exact ISO action date required')
    return parsed


def number(value):
    try:
        if isinstance(value, bool) or value is None:
            raise ValueError('Finite positive action term required')
        result = Decimal(str(value))
        if not result.is_finite() or result <= 0:
            raise ValueError('Finite positive action term required')
        return result
    except InvalidOperation as exc:
        raise ValueError('Finite positive action term required') from exc


def candidate(provider, kind, record, *, scoped_symbols, start, end, source):
    """Select full-window source-symbol facts without inventing effect dates."""
    roles = symbols(record)
    selected = sorted({r['symbol'] for r in roles}.intersection(scoped_symbols))
    if not selected:
        return None
    identifier = record.get('id')
    if not isinstance(identifier, str) or not identifier:
        raise ValueError('Original action identity required')
    if provider == 'massive' and kind in ('dividends', 'splits'):
        field = 'ex_dividend_date' if kind == 'dividends' else 'execution_date'
        category = 'cash' if kind == 'dividends' else 'split'
        subject = record.get('ticker')
    elif provider == 'alpaca':
        # Process date is never a substitute effective or publication date.
        field = 'ex_date' if record.get('ex_date') else 'effective_date'
        category = SIMPLE.get(kind, 'complex')
        subject = record.get('symbol') if category != 'complex' else None
    else:
        raise ValueError('Known provider/action category required')
    effective = iso_day(record[field]) if record.get(field) else None
    process = iso_day(record['process_date']) if record.get('process_date') else None
    if effective is not None:
        if not start <= effective <= end:
            return None
    elif process is None or not start <= process <= end:
        return None
    problems = []
    term = None
    try:
        if category == 'cash':
            if provider == 'massive' and record.get('currency') != 'USD':
                problems.append('non_usd_or_unknown_currency')
            if provider == 'alpaca' and record.get('foreign') is not False:
                problems.append('foreign_or_unspecified_cash_units')
            term = number(record['cash_amount'] if provider == 'massive' else record.get('rate'))
        elif category == 'split':
            if provider == 'massive' and record.get('adjustment_type') not in ('forward_split', 'reverse_split'):
                problems.append('not_a_declared_simple_split')
            old = number(record['split_from'] if provider == 'massive' else record.get('old_rate'))
            new = number(record['split_to'] if provider == 'massive' else record.get('new_rate'))
            # Preserve the reported ratio; cross-provider reconciliation still
            # cannot prove actual share delivery (e.g. a spin-off encoded here).
            term = new / old
    except (ValueError, KeyError):
        problems.append('invalid_or_missing_event_term')
    if effective is None:
        problems.append('missing_effective_date')
    if category != 'complex' and subject not in selected:
        problems.append('subject_outside_scope')
    return dict(provider=provider, kind=kind, action_id=identifier, category=category,
        subject_symbol=subject, scoped_symbols=selected, symbol_roles=roles,
        effective_date=effective, effective_field=field if effective else None,
        process_date=process, term=str(term) if term is not None else None,
        term_basis={'cash': 'provider_reported_cash_amount', 'split': 'provider_reported_split_ratio',
                    'complex': 'requires_event_specific_review'}[category],
        term_issues=problems, source=source, record_sha256=identity(record), record=record,
        publication_verified=False, security_identity_verified=False, research_ready=False)


def reconcile(candidates, eligible_identities):
    """Exact symbol/day evidence only; no nearest-date or static-alias matching."""
    groups, complex_days = defaultdict(list), defaultdict(list)
    seen = set()
    for row in candidates:
        key = row['provider'], row['kind'], row['action_id']
        if key in seen:
            raise ValueError('Duplicate captured action identity')
        seen.add(key)
        if row['category'] != 'complex' and row['effective_date'] and row['subject_symbol'] in row['scoped_symbols']:
            groups[(row['subject_symbol'], row['effective_date'], row['category'])].append(row)
        else:
            for symbol in row['scoped_symbols']:
                complex_days[(symbol, row['effective_date'])].append(row['action_id'])
    categories = defaultdict(set)
    for symbol, day, category in groups:
        categories[(symbol, day)].add(category)
    result = []
    for (symbol, day, category), rows in sorted(groups.items()):
        providers = {p: [r for r in rows if r['provider'] == p] for p in ('massive', 'alpaca')}
        issues = sorted({issue for r in rows for issue in r['term_issues']})
        totals = {}
        for provider, observations in providers.items():
            if observations and all(r['term'] is not None for r in observations):
                values = [Decimal(r['term']) for r in observations]
                if category == 'cash':
                    totals[provider] = str(sum(values))
                elif len(values) == 1:
                    totals[provider] = str(values[0])
        multiple = any(len(values) > 1 for values in providers.values())
        combined = len(categories[(symbol, day)]) > 1 or bool(complex_days.get((symbol, day)))
        if issues:
            status = 'unreviewed_terms'
        elif any(not observations for observations in providers.values()):
            status = 'single_provider'
        elif set(totals) != {'massive', 'alpaca'}:
            status = 'ambiguous_multiple_events'
        elif Decimal(totals['massive']) != Decimal(totals['alpaca']):
            status = 'term_mismatch'
        elif multiple or combined:
            status = 'matching_total_requires_combined_review'
        else:
            status = 'matching_single_event_terms'
        identities = sorted(eligible_identities.get((symbol, day), set()))
        if len(identities) > 1:
            raise ValueError('Ambiguous active action-day security identity')
        result.append(dict(symbol=symbol, effective_date=day, category=category, status=status,
            provider_action_ids={p: [r['action_id'] for r in observations] for p, observations in providers.items()},
            provider_terms=totals, term_issues=issues, multiple_records=multiple,
            combined_event_day=combined, complex_action_ids=complex_days.get((symbol, day), []),
            eligible_security_id=identities[0] if identities else None,
            identity_status='exact_active_session' if identities else 'outside_active_session_unassigned',
            publication_verified=False, combined_semantics_verified=False, research_ready=False))
    return result
