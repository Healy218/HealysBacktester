"""Explicit action coverage over selected histories, without absence inference.

An admitted event covers its own terms only. A quiet provider response is an
observation about that capture, not a proof that no unreported event existed.
"""
from collections import defaultdict

import pandas as pd

from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.ordinary_actions import price_action
from nn_meta.v7.storage import identity


def validate_coverage_policy(policy):
    if (policy.get('schema') != 'v7-no-event-reconstruction-admission-v1'
            or policy.get('status') != 'user_authorized'
            or policy.get('policy_id') != 'provider-union-no-event-reconstruction-20260917'
            or policy.get('proposed_basis') != 'retrospective_provider_union_completeness_assumption'
            or policy.get('scope_change') is not False or policy.get('research_ready') is not False
            or not policy.get('authorization') or len(policy.get('conditions', [])) != 7):
        raise ValueError('Explicit authorized no-event reconstruction policy required')
    return identity(policy)


def coverage_panel(history, candidates, events, unresolved, *, policy=None, other_instruments=(), renames=()):
    """Reconcile every original record before classifying every history row.

    Undated records block every date routed through an involved symbol. Dated
    records block their effective date. Neither is discarded for falling outside
    entry membership: feature lookbacks and held positions can still need them.
    """
    keys = ['security_id', 'source_date']
    if (history.empty or not set(keys + ['stock_ticker', 'source_status']).issubset(history)
            or history.duplicated(keys).any() or history.security_id.isna().any()):
        raise ValueError('Unique full selected security history required')
    policy_id = validate_coverage_policy(policy) if policy is not None else None
    originals = {}
    for row in candidates:
        key = record_key(row)
        if key in originals or row['record_sha256'] != identity(row['record']):
            raise ValueError('Duplicate or changed original action record')
        originals[key] = row
    facts = history.set_index(keys)
    consumed, event_days = set(), {}
    for event in events:
        action = price_action(event)
        day = action.effective_at.tz_convert('America/New_York').date().isoformat()
        key = event['security_id'], day
        if key in event_days:
            raise ValueError('One reviewed combined event per security session required')
        match = facts.loc[key] if key in facts.index else None
        if match is None or pd.isna(match.stock_ticker) or match.stock_ticker != event['symbol']:
            raise ValueError('Compiled event does not match selected history')
        event_days[key] = action.event_id
        for reference in event['replaces']:
            rkey = record_key(reference)
            if (rkey in consumed or rkey not in originals
                    or reference['record_sha256'] != originals[rkey]['record_sha256']):
                raise ValueError('Compiled event source partition differs')
            consumed.add(rkey)
    for treatment in other_instruments:
        if (treatment.get('treatment') != 'reviewed_unrelated_instrument'
                or not treatment.get('review_identity') or not treatment.get('listed_record_sha256')
                or not treatment.get('other_share_class_figi')
                or treatment.get('other_security_id') in set(history.security_id)
                or not treatment.get('replaces')):
            raise ValueError('Bound reviewed unrelated-instrument treatment required')
        for reference in treatment['replaces']:
            rkey = record_key(reference)
            if (rkey in consumed or rkey not in originals
                    or reference['record_sha256'] != originals[rkey]['record_sha256']):
                raise ValueError('Unrelated-instrument source partition differs')
            consumed.add(rkey)
    from nn_meta.v7.renames import require_rename_history
    identity_days = {}
    for event in renames:
        require_rename_history(event, history)
        key = event['security_id'], event['effective_date']
        if key in identity_days or len(event.get('replaces', [])) != 1:
            raise ValueError('Unique original name-change treatment required')
        ref = event['replaces'][0]; rkey = record_key(ref)
        original = originals.get(rkey)
        if (rkey in consumed or original is None or rkey[:2] != ('alpaca', 'name_changes')
                or ref['record_sha256'] != original['record_sha256']
                or original['record']['old_symbol'] != event['old_symbol']
                or original['record']['new_symbol'] != event['new_symbol']):
            raise ValueError('Rename original-record partition differs')
        consumed.add(rkey); identity_days[key] = event['event_id']
    pending, dated, undated = set(), defaultdict(set), defaultdict(set)
    for row in unresolved:
        key = record_key(row)
        if (key in pending or key in consumed or key not in originals
                or {k: row[k] for k in originals[key]} != originals[key]):
            raise ValueError('Unresolved source partition differs')
        pending.add(key)
        identifier = identity(dict(provider=key[0], kind=key[1], action_id=key[2]))
        for symbol in row['scoped_symbols']:
            if row['effective_date'] is None:
                undated[symbol].add(identifier)
            else:
                dated[symbol, row['effective_date']].add(identifier)
    if consumed | pending != set(originals):
        raise ValueError('Every original record needs exactly one explicit treatment')
    # A held position can retain its previous ticker. Keep pending alias records
    # visible until exact identity/role review proves them irrelevant.
    security_symbols = history[history.stock_ticker.notna()].groupby('security_id').stock_ticker.agg(set).to_dict()
    security_undated = {sid: set().union(*(undated.get(s, set()) for s in symbols))
                        for sid, symbols in security_symbols.items()}
    rows = []
    for row in history.itertuples(index=False):
        known = pd.notna(row.stock_ticker) and row.source_status in ('observed', 'listed_no_stock_observation')
        blocked = sorted(security_undated.get(row.security_id, set()) | set().union(
            *(dated.get((s, row.source_date), set()) for s in security_symbols.get(row.security_id, set())))) if known else []
        event = event_days.get((row.security_id, row.source_date))
        status = ('unresolved_identity' if not known else 'unresolved_action_records' if blocked
                  else 'compiled_event_only' if event else 'no_event_not_established')
        admitted = bool(policy_id and known and not blocked)
        if admitted:
            status = 'compiled_event_with_assumed_coverage' if event else 'assumed_no_event'
        rows.append(dict(security_id=row.security_id, source_date=row.source_date,
            stock_ticker=row.stock_ticker, coverage_status=status, event_id=event,
            identity_event_id=identity_days.get((row.security_id, row.source_date)),
            unresolved_record_ids=blocked, history_admitted=admitted,
            coverage_policy_identity=policy_id, completeness_verified=False,
            held_position_admitted=False))
    result = pd.DataFrame(rows)
    result.attrs['coverage_basis'] = ('retrospective_provider_union_completeness_assumption' if policy_id
                                    else 'captured_records_only_no_absence_inference')
    return result


def require_history_coverage(coverage, *, security_id, dates, held=False):
    """Consumer guard: missing dates or unknown coverage never mean factor one."""
    dates = list(dates)
    if not dates or dates != sorted(set(dates)) or not security_id:
        raise ValueError('Exact ordered required history dates and security required')
    field = 'held_position_admitted' if held else 'history_admitted'
    if (not {'security_id', 'source_date', field}.issubset(coverage)
            or coverage.duplicated(['security_id', 'source_date']).any()):
        raise ValueError('Unique dated coverage declaration required')
    selected = coverage[coverage.security_id.eq(security_id) & coverage.source_date.isin(dates)]
    if (set(selected.source_date) != set(dates)
            or not selected[field].map(lambda x: type(x) is bool and x).all()):
        raise ValueError('Required history has unresolved action or identity coverage')
    return selected.sort_values('source_date').copy()
