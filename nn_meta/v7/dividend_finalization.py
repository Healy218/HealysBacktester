"""Final cash-dividend audit, retaining independent security lifecycle gates."""
from decimal import Decimal
import math
import pandas as pd
from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.dividend_components import validate_components
from nn_meta.v7.dividend_closure import dividend_census
from nn_meta.v7.dividend_dispositions import coverage_with_dispositions
from nn_meta.v7.ordinary_actions import price_action


def final_dividend_audit(originals,actions,events,pending,other,renames,history,boundary_history,
                         boundary_requests,calendar,schedule,coverage_policy):
    grouped=validate_components(actions,events,calendar,schedule)
    census,uncompiled,missing=dividend_census(originals,actions,other,renames,
        [v[0] for v in grouped.values()],pending)
    if uncompiled or missing or len(grouped)!=census['compiled_cash_actions']:
        raise ValueError('Every original dividend needs its complete price and held-cash treatment')
    if any(r['category']=='cash' for r in pending):raise ValueError('Unresolved cash cannot pass finalization')
    base=history.set_index(['security_id','source_date'])
    boundary=boundary_history.set_index(['security_id','source_date'])
    if not base.index.is_unique or not boundary.index.is_unique:raise ValueError('Unique security sessions required')
    requests={(r['security_id'],r['ex_date']):r for r in boundary_requests}
    sessions=sorted(calendar.sessions);auxiliary=[];canonical=[];factor_checks=[]
    for event in actions:
        action=price_action(event);day=action.effective_at.tz_convert('America/New_York').date().isoformat()
        if event.get('effective_date',day)!=day:raise ValueError('Action date differs from its effective clock')
        key=event['security_id'],day
        selected=base.loc[key] if key in base.index else None
        matches=selected is not None and pd.notna(selected.stock_ticker) and selected.stock_ticker==event['symbol']
        if not matches:
            request=requests.get(key)
            if (event['category']!='cash' or request is None or request['source_symbol']!=event['symbol']
                    or request['changes_trading_eligibility'] is not False
                    or request['bridges_reorganization'] is not False
                    or key not in boundary.index or boundary.loc[key,'stock_ticker']!=event['symbol']
                    or not bool(boundary.loc[key,'dividend_boundary_only'])):
                raise ValueError('Noncanonical cash needs its exact independent boundary treatment')
            auxiliary.append(event)
        else:canonical.append(event)
        if event['category']!='cash':continue
        prior=sessions[sessions.index(day)-1]
        keys=[(event['security_id'],d) for d in (prior,day)]
        if any(k not in boundary.index for k in keys):raise ValueError('Actual raw dividend boundary missing')
        prev,now=[boundary.loc[k] for k in keys]
        if (pd.isna(prev.identity_span) or prev.identity_span!=now.identity_span
                or prev.observed_minutes<=0 or now.observed_minutes<=0
                or prev.available_ns!=calendar.bounds(prior)[1].tz_localize('UTC').value
                or action.effective_at.value!=calendar.bounds(day)[0].tz_localize('UTC').value):
            raise ValueError('Dividend cannot cross missing identity or raw observations')
        amount=Decimal(event['cash_amount']);close=float(prev.raw_close)
        expected=(close-float(amount))/close
        if not math.isclose(action.price_factor,expected,rel_tol=1e-12,abs_tol=1e-14):
            raise ValueError('Cash and price factor differ on actual raw history')
        factor_checks.append(dict(event_id=action.event_id,security_id=event['security_id'],
            ex_date=day,prior_date=prior,prior_raw_close=close,cash_amount=str(amount),price_factor=action.price_factor))
    # The full original partition is already proven above. Its finite auxiliary
    # cash events are independently validated, and do not admit canonical study
    # rows whose security identity remains unknown.
    aux_keys={record_key(r) for a in auxiliary for r in a['replaces']}
    canonical_ids={a['action']['event_id'] for a in canonical}
    dispositions=[t for t in other if t.get('schema')=='v7-reviewed-dividend-disposition-v1']
    legacy=[t for t in other if t not in dispositions]
    coverage=coverage_with_dispositions(history,[r for r in originals if record_key(r) not in aux_keys],
        canonical,pending,dispositions,policy=coverage_policy,other=legacy,renames=renames,
        cash=[e for e in events if e['compiled_event_id'] in canonical_ids])
    if (len(coverage)!=len(history) or set(map(tuple,coverage[['security_id','source_date']].to_numpy()))!=set(base.index)
            or coverage.held_position_admitted.any()):raise ValueError('Dividend closure cannot expand history or admit held lifecycles')
    report=dict(census,dividends_complete=True,total_cash_payments=len(events),
        verified_cash_price_boundaries=len(factor_checks),auxiliary_cash_price_events=len(auxiliary),
        original_history_rows=len(history),admitted_history_sessions=int(coverage.history_admitted.sum()),
        scope='cash classification, price factors and pretax funded-share entitlements; lifecycle transitions remain separate',
        settlement_coverage=[schedule.document['coverage_start'],schedule.document['coverage_end']],
        modeled_fx_payments=sum(e.get('cash_amount_basis')=='authorized_modeled_official_fx' for e in events),
        provider_precision_payments=sum(e.get('cash_amount_basis')=='paired_provider_decimal_precision' for e in events),
        changes_trading_eligibility=False,held_position_admitted=False)
    report['limitations']=[
        'Effective-session availability is retrospective reconstruction, not historical publication proof',
        f"{report['modeled_fx_payments']} cash payments use explicitly authorized modeled FX, not actual depositary conversion",
        'ETHE September amount/date are from a decimal-reconciled provider pair; primary notice unavailable',
        'Auxiliary cash securities do not bridge predecessor/successor holdings or add entry eligibility',
        'Broker postings, withholding/fees, noncash lifecycle and option deliverables remain separate',
        'No strategy replay, training, deployment or overall step-1 admission is claimed']
    return report,coverage,auxiliary,factor_checks
