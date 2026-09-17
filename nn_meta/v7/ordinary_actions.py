"""Explicitly assumed effective-session reconstruction of matching actions.

This admits individual chart adjustments, not full no-event histories, stock
entitlements or option deliverables. Reviewed whole-event corrections win once.
"""
from collections import defaultdict
from dataclasses import asdict, dataclass
import math

import pandas as pd

from nn_meta.v7.action_inventory import candidate, number, reconcile
from nn_meta.v7.cash_actions import compile_cash_actions, record_key
from nn_meta.v7.causal_prices import PriceAction, cash_distribution_action, split_action
from nn_meta.v7.storage import identity

BASIS = 'matching_provider_historical_reconstruction'
POLICY_ID = 'matching-provider-effective-session-reconstruction-20260917'


@dataclass(frozen=True)
class ReconstructionAction(PriceAction):
    """PriceAction-compatible input whose availability is explicitly assumed."""
    admission_policy_identity: str
    admission_basis: str = BASIS
    publication_available_at: None = None
    publication_verified: bool = False

    def __post_init__(self):
        super().__post_init__()
        if (not self.admission_policy_identity or self.admission_basis != BASIS
                or self.available_at != self.effective_at
                or self.publication_available_at is not None
                or self.publication_verified is not False):
            raise ValueError('Explicit effective-session assumption; no publication claim allowed')


def validate_policy(policy):
    expected = dict(schema='v7-ordinary-action-admission-v1', policy_id=POLICY_ID,
        admission_basis=BASIS, providers=['alpaca', 'massive'], categories=['cash', 'split'],
        unique_record_per_provider=True, exact_terms_and_effective_date=True,
        require_dated_security_continuity=True,
        available_at_basis='effective_session_open_assumption_not_publication',
        publication_verified=False, reviewed_whole_event_replacements_take_precedence=True,
        no_event_coverage_inferred=False, option_deliverables_inferred=False,
        combined_or_complex_actions_admitted=False, duplicate_records_summed_or_deduplicated=False,
        unknown_currency_or_units_admitted=False, full_security_admitted=False)
    if any(policy.get(k) != v or type(policy.get(k)) != type(v) for k, v in expected.items()):
        raise ValueError('Explicit unchanged authorized ordinary-action policy required')
    return identity(policy)


def serialized_action(action):
    value = asdict(action)
    for field in ('effective_at', 'available_at'):
        value[field] = value[field].isoformat()
    return value


def price_action(event):
    """Load an individual compiled input without erasing its admission basis."""
    if event['admission_basis'] == BASIS:
        action = ReconstructionAction(**event['action'])
        if action.admission_policy_identity != event['admission_policy_identity']:
            raise ValueError('Action policy binding differs from event')
    elif event['admission_basis'] == 'reviewed_publication':
        action = PriceAction(**event['action'])
    else:
        raise ValueError('Unknown compiled action admission basis')
    if event['full_security_admitted'] is not False:
        raise ValueError('An individual event cannot admit a complete history')
    return action


def compile_ordinary_actions(candidates, reviews, history, calendar, policy):
    """Partition every input record, compiling only supported whole groups.

    History is exact-day selected raw data, including nonmembership sessions.
    No prices or security IDs propagate through absent or ambiguous dates.
    Unsupported groups remain explicit; never convert them to factor one.
    """
    policy_identity = validate_policy(policy)
    candidates, reviews = list(candidates), list(reviews)
    by_key, groups = {}, defaultdict(list)
    for row in candidates:
        key = record_key(row)
        rebuilt = candidate(row['provider'], row['kind'], row['record'],
            scoped_symbols=set(row['scoped_symbols']), start=calendar.start, end=calendar.end,
            source=row['source'])
        if key in by_key or rebuilt != row:
            raise ValueError('Duplicate or changed normalized/original action record')
        by_key[key] = row
        if row['category'] != 'complex' and row['effective_date']:
            groups[row['subject_symbol'], row['effective_date'], row['category']].append(row)
    required = {'stock_ticker', 'source_date', 'security_id', 'identity_span',
                'observed_minutes', 'raw_close', 'available_ns', 'session_open_ns'}
    if (not required.issubset(history) or history.duplicated(['security_id', 'source_date']).any()
            or history.security_id.isna().any()
            or history[history.stock_ticker.notna()].duplicated(['stock_ticker', 'source_date']).any()):
        raise ValueError('Unique dated selected security histories required')
    selected = history[history.stock_ticker.notna()]
    facts = selected.set_index(['stock_ticker', 'source_date'])
    by_security = history.set_index(['security_id', 'source_date'])
    sessions = sorted(calendar.sessions)
    positions = {day: i for i, day in enumerate(sessions)}
    # Existing publication reviews retain their exact evidence and correction.
    reviewed, _ = compile_cash_actions(candidates, reviews, selected, calendar)
    events = [dict(e, category='cash', admission_basis='reviewed_publication',
                   admission_policy_identity=policy_identity) for e in reviewed]
    consumed = {record_key(r) for e in events for r in e['replaces']}
    clocks = {(e['security_id'], e['action']['effective_at']) for e in events}
    decisions, reasons = [], {}
    for group in reconcile(candidates, {}):
        symbol, day, category = group['symbol'], group['effective_date'], group['category']
        rows = groups[symbol, day, category]
        keys = {record_key(r) for r in rows}
        decision = dict(symbol=symbol, effective_date=day, category=category,
            inventory_status=group['status'], provider_records=len(rows), security_id=None)
        if keys & consumed:
            if not keys <= consumed:
                raise ValueError('Reviewed replacement consumed only part of an event group')
            decision['treatment'] = 'reviewed_whole_event'
            decisions.append(decision)
            continue
        reason = None
        if group['status'] != 'matching_single_event_terms':
            reason = group['status']
        elif day not in positions or positions[day] == 0:
            reason = 'missing_preceding_calendar_session'
        elif (symbol, day) not in facts.index:
            reason = 'missing_selected_effective_identity'
        else:
            current = facts.loc[(symbol, day)]
            security = current.security_id
            decision['security_id'] = security
            prior_day = sessions[positions[day] - 1]
            prior = by_security.loc[(security, prior_day)] if (security, prior_day) in by_security.index else None
            if (prior is None or pd.isna(current.identity_span) or pd.isna(prior.identity_span)
                    or current.identity_span != prior.identity_span):
                reason = 'missing_adjacent_security_continuity'
            else:
                effective = calendar.bounds(day)[0].tz_localize('UTC')
                close = calendar.bounds(prior_day)[1].tz_localize('UTC')
                if (pd.isna(current.session_open_ns) or current.session_open_ns != effective.value
                        or pd.isna(prior.available_ns) or prior.available_ns != close.value):
                    raise ValueError('Selected history clocks differ from captured calendar')
                if category == 'cash' and (pd.isna(prior.observed_minutes) or prior.observed_minutes <= 0
                        or pd.isna(prior.raw_close) or not math.isfinite(prior.raw_close) or prior.raw_close <= 0):
                    reason = 'missing_observed_prior_close'
                elif category == 'cash' and number(rows[0]['term']) >= number(prior.raw_close):
                    reason = 'cash_not_below_prior_close'
        if reason:
            decision['treatment'] = reason
            decisions.append(decision)
            for key in keys:
                reasons[key] = reason
            continue
        references = [{k: r[k] for k in ('provider', 'kind', 'action_id', 'record_sha256')}
                      for r in sorted(rows, key=record_key)]
        terms = number(rows[0]['term'])
        evidence = dict(policy_identity=policy_identity, replaces=references,
            security_id=security, identity_span=current.identity_span,
            prior_source_date=prior_day, prior_stock_ticker=prior.stock_ticker,
            effective_date=day, symbol=symbol, category=category, term=str(terms),
            prior_raw_close=float(prior.raw_close) if category == 'cash' else None)
        source_identity = identity(evidence)
        event_id = 'reconstructed-' + source_identity
        kwargs = dict(event_id=event_id, effective_at=effective, available_at=effective,
                      source_identity=source_identity)
        base = (cash_distribution_action(cash_per_share=float(terms), prior_raw_close=float(prior.raw_close),
                    prior_close_at=close, **kwargs) if category == 'cash'
                else split_action(old_shares=1., new_shares=float(terms), **kwargs))
        action = ReconstructionAction(**asdict(base), admission_policy_identity=policy_identity)
        clock = security, effective.isoformat()
        if clock in clocks:
            raise ValueError('Multiple selected actions at one security clock require combined review')
        clocks.add(clock)
        events.append(dict(symbol=symbol, security_id=security, effective_date=day, category=category,
            admission_basis=BASIS, admission_policy_identity=policy_identity, evidence=evidence,
            publication_available_at=None, publication_verified=False, replaces=references,
            cash_amount=str(terms) if category == 'cash' else None,
            new_shares_per_old_share=str(terms) if category == 'split' else None,
            cash_units='USD_per_listed_share_or_unit' if category == 'cash' else None,
            action=serialized_action(action), full_security_admitted=False,
            held_position_treatment='requires_entitlement_and_deliverable_evidence'))
        consumed.update(keys)
        decision.update(treatment='compiled_historical_reconstruction', event_id=event_id)
        decisions.append(decision)
    pending = [dict(r, compilation_reason=reasons.get(record_key(r), 'complex_event_specific_review'))
               for r in candidates if record_key(r) not in consumed]
    if sum(len(e['replaces']) for e in events) + len(pending) != len(candidates):
        raise ValueError('Compiled events do not partition original records')
    return events, pending, decisions
