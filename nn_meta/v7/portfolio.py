"""Chronological shared allocation over observed, independently replayed quote paths.

The path supplies market events, never a ranking feature or eligibility filter.
Missing outcomes remain in the portfolio and prevent evaluation admission.
"""
import heapq
import math
import pandas as pd

from nn_meta.v7.execution import CashLedger, QuotePolicy, QuoteUnavailable, CaptureUnavailable, fill_clock


def portfolio_replay(candidates, clocks, archive, *, capital=100000., slots=5, fraction=.1,
                     policy=QuotePolicy(), physical=None, noncash_boundaries=None):
    candidates = list(candidates)
    clocks = list(clocks)
    if not clocks or clocks != sorted(set(clocks)) or any(type(t) is not int for t in clocks):
        raise ValueError('Ordered unique valuation clocks required')
    ids = [p['proposal_id'] for p in candidates]
    if len(set(ids)) != len(ids):
        raise ValueError('Distinct proposal identities required')
    if physical is None:
        ledger = CashLedger(capital=capital, slots=slots, fraction=fraction, policy=policy)
    else:
        from nn_meta.v7.physical import PhysicalLedger
        ledger = PhysicalLedger(capital=capital, slots=slots, fraction=fraction, policy=policy,
            settlement_calendar=physical.settlement_calendar, physical_policy=physical.policy)
    queue, serial = [], 0
    def event(clock, priority, kind, payload):
        nonlocal serial
        serial += 1
        heapq.heappush(queue, (clock, priority, serial, kind, payload))
    batches = {}
    by_id = {}
    for item in candidates:
        p = dict(item)
        if noncash_boundaries is not None and p.get('security_id') and p.get('source_dates'):
            from nn_meta.v7.noncash_admission import require_boundary_safe
            require_boundary_safe(noncash_boundaries, security_id=p['security_id'],
                                  source_dates=p['source_dates'])
        clock = p['decision_ns']
        if (type(clock) is not int or clock < clocks[0] or clock > clocks[-1]
                or not math.isfinite(p['score']) or type(p['score_available_ns']) is not int
                or p['score_available_ns'] > clock):
            raise ValueError('Causal finite decision score required')
        path = p['path']
        if path['proposal_id'] != p['proposal_id']:
            raise ValueError('Quote path belongs to another proposal')
        previous = clock
        for i, fill in enumerate(path['fills']):
            if (fill_clock(fill) < previous or fill['side'] != ('buy' if i % 2 == 0 else 'sell')
                    or fill['decision_ns'] < clock or fill['decision_ns'] > fill_clock(fill)
                    or fill['sip_timestamp'] > fill_clock(fill)):
                raise ValueError('Quote path has invalid event chronology')
            previous = fill_clock(fill)
        by_id[p['proposal_id']] = p
        batches.setdefault(clock, []).append(p)
    for clock in clocks:
        event(clock, 1, 'mark', None)
    for clock, batch in batches.items():
        event(clock, 2, 'decide', sorted(batch, key=lambda p: (-p['score'], p['proposal_id'])))
    if physical is not None:
        from nn_meta.v7.stock_splits import stock_split_terms
        for split in getattr(physical, 'splits', ()):
            _,clock,_=stock_split_terms(split,physical.settlement_calendar.trading)
            if clocks[0]<=clock<=clocks[-1]:
                event(clock,-1,'stock_split',split)
        from nn_meta.v7.renames import validate_rename
        for rename in getattr(physical, 'renames', ()):
            validate_rename(rename)
            if clocks[0] <= rename['effective_ns'] <= clocks[-1]:
                event(rename['effective_ns'], -1, 'stock_rename', rename)
        from nn_meta.v7.stock_cash import validate_cash_event
        for cash_event in getattr(physical, 'cash_entitlements', ()):
            if clocks[0] <= cash_event['effective_ns'] <= clocks[-1]:
                validate_cash_event(cash_event, physical.settlement_calendar.trading,
                                    settlement_calendar=physical.settlement_calendar)
                event(cash_event['effective_ns'], -1, 'cash_accrual', cash_event)
                event(cash_event['release_ns'], -2, 'cash_release', cash_event)
    active, reservations, decisions, marks = {}, {}, [], []
    completed, capture_complete = set(), True

    def equity(clock):
        if physical is not None:
            class Tapes:
                def __getitem__(self, contract):
                    class Tape:
                        def mark(self, at):
                            return archive.mark(contract, at)
                    return Tape()
            return ledger.equity(clock, Tapes(), physical.stock_archive)
        return ledger.cash + sum(position['quantity'] * policy.multiplier *
            archive.mark(position['contract'], clock)['price'] for position in ledger.positions.values())

    while queue:
        clock, _, _, kind, payload = heapq.heappop(queue)
        if clock > clocks[-1]:
            break
        if kind == 'stock_split':
            ledger.apply_stock_split(payload, clock)
        elif kind == 'cash_accrual':
            ledger.accrue_stock_cash(payload, clock)
        elif kind == 'cash_release':
            ledger.release_stock_cash(payload, clock)
        elif kind == 'stock_rename':
            affected = ledger.apply_stock_rename(payload, clock)
            for key in affected:
                if key in active:
                    active[key]['symbol'] = payload['new_symbol']
        elif kind == 'mark':
            if physical is not None:
                ledger.settle(clock)
                for key in list(active):
                    if key in ledger.completed:
                        reservations.pop(key, None)
                        active.pop(key)
                        completed.add(key)
                for key, position in list(ledger.positions.items()):
                    if position.get('phase') != 'stock':
                        continue
                    try:
                        fill = physical.stock_archive.first_fill(position['symbol'], clock, side='sell',
                            quantity=position['deliverable_shares'])
                        if fill is not None:
                            event(fill['sip_timestamp'], 0, 'stock_fill', (key, fill))
                    except CaptureUnavailable:
                        capture_complete = False
            try:
                marks.append({'clock_ns': clock, 'equity': equity(clock), 'status': 'observed'})
            except CaptureUnavailable as exc:
                capture_complete = False
                marks.append({'clock_ns': clock, 'status': 'uncaptured', 'error': str(exc)})
            except QuoteUnavailable as exc:
                marks.append({'clock_ns': clock, 'status': 'unavailable', 'error': str(exc)})
        elif kind == 'decide':
            for p in payload:
                key = p['proposal_id']
                why = None
                if any(s['symbol'] == p['symbol'] for s in active.values()):
                    why = 'symbol_occupied'
                elif len(active) >= slots:
                    why = 'slots_full'
                else:
                    try:
                        value = equity(clock)
                    except CaptureUnavailable:
                        capture_complete, why = False, 'equity_capture_missing'
                    except QuoteUnavailable:
                        why = 'equity_unavailable'
                if why:
                    decisions.append({'proposal_id': key, 'clock_ns': clock, 'status': why})
                    continue
                available = ledger.cash - sum(reservations.values()) if physical is None else ledger.available_cash
                budget = min(available, fraction * value)
                if budget <= 0:
                    decisions.append({'proposal_id': key, 'clock_ns': clock, 'status': 'no_cash'})
                    continue
                reservations[key] = budget
                if physical is not None and not ledger.reserve_entry(key, budget):
                    raise ValueError('Physical ledger refused an available reservation')
                active[key] = {'symbol': p['symbol'], 'entry_budget': budget}
                decisions.append({'proposal_id': key, 'clock_ns': clock, 'status': 'reserved', 'budget': budget})
                # Inspecting the simulated path here only schedules its market
                # events. Success/failure/return never affects acceptance above.
                path = p['path']
                capture_complete &= path['capture_complete']
                for fill in path['fills']:
                    event(fill_clock(fill), 0, 'fill', (key, fill))
                if not path['fills']:
                    event(clock + policy.entry_deadline_ns, 0, 'unfilled', key)
                elif path['label_complete']:
                    end = path['label_end_ns']
                    if end < fill_clock(path['fills'][-1]):
                        raise ValueError('Terminal label precedes a market fill')
                    event(end, 0, 'terminal', key)
        elif kind == 'fill':
            key, fill = payload
            p = by_id[key]
            if fill['side'] == 'buy':
                budget = reservations.pop(key)
                date = pd.Timestamp(fill['decision_ns'], unit='ns', tz='UTC').tz_convert('America/New_York').date()
                if not ledger.buy(key, p['symbol'], fill, equity=max(ledger.cash, budget),
                                  budget=budget, decision_date=date, roll_of=fill.get('roll_of'),
                                  **({'security_id': p['security_id']} if physical is not None else {})):
                    raise ValueError('Reserved portfolio purchase was unexpectedly rejected')
                if physical is not None:
                    expiry_ns = physical.exercise_clock(fill['contract'])
                    if expiry_ns <= clock:
                        raise ValueError('Exercise clock must follow the purchase')
                    event(expiry_ns, 0, 'exercise', (key, fill['contract']))
            else:
                reservations[key] = ledger.sell(key, fill)
                if physical is not None and not ledger.reserve_entry(key, reservations[key]):
                    raise ValueError('Roll proceeds could not be reserved')
        elif kind == 'exercise':
            key, contract = payload
            position = ledger.positions.get(key)
            if position is None or position['contract'] != contract or position.get('phase') != 'option':
                continue
            try:
                evidence = physical.expiry_evidence(contract)
                status = ledger.expire(key, clock, **evidence)
            except CaptureUnavailable:
                capture_complete, status = False, 'expiry_evidence_uncaptured'
            decisions.append({'proposal_id': key, 'clock_ns': clock, 'status': status})
            if key in ledger.completed:
                active.pop(key)
                completed.add(key)
        elif kind == 'stock_fill':
            key, fill = payload
            if ledger.positions[key]['phase'] == 'stock':
                ledger.liquidate_stock(key, fill)
        elif kind in ('terminal', 'unfilled'):
            if payload in ledger.positions:
                raise ValueError('Cannot release an unresolved position slot')
            reservations.pop(payload, None)
            if physical is not None:
                ledger.entry_reservations.pop(payload, None)
            active.pop(payload)
            completed.add(payload)
    ledger.reconcile()
    return {'cash': ledger.cash, 'reserved_cash': sum(reservations.values()),
            'physical_completed_at': dict(ledger.completed) if physical is not None else {},
            'physical_commitments': dict(ledger.commitments) if physical is not None else {},
            'physical_cash_receivables': dict(ledger.cash_receivables) if physical is not None else {},
            'open_positions': ledger.positions, 'active_proposals': active,
            'fills': ledger.events, 'decisions': decisions, 'marks': marks,
            'capture_complete': capture_complete,
            'complete': not active and capture_complete and (physical is None or not ledger.cash_receivables),
            'valuation_complete': all(m['status'] == 'observed' for m in marks),
            'completed_proposals': sorted(completed),
            'allocation_policy': {'capital': capital, 'slots': slots, 'fraction': fraction,
                'one_position_per_symbol_across_timeframes': True,
                'order': 'descending causal score, then ascending proposal_id',
                'unavailable_held_mark': 'pause new entries; continue observed exits',
                'fractional_paper': True}}
