"""Chronological shared allocation over observed, independently replayed quote paths.

The path supplies market events, never a ranking feature or eligibility filter.
Missing outcomes remain in the portfolio and prevent evaluation admission.
"""
import heapq
import math
import pandas as pd

from nn_meta.v7.execution import CashLedger, QuotePolicy, QuoteUnavailable, CaptureUnavailable


def portfolio_replay(candidates, clocks, archive, *, capital=100000., slots=5, fraction=.1,
                     policy=QuotePolicy()):
    candidates = list(candidates)
    clocks = list(clocks)
    if not clocks or clocks != sorted(set(clocks)) or any(type(t) is not int for t in clocks):
        raise ValueError('Ordered unique valuation clocks required')
    ids = [p['proposal_id'] for p in candidates]
    if len(set(ids)) != len(ids):
        raise ValueError('Distinct proposal identities required')
    ledger = CashLedger(capital=capital, slots=slots, fraction=fraction, policy=policy)
    queue, serial = [], 0
    def event(clock, priority, kind, payload):
        nonlocal serial
        serial += 1
        heapq.heappush(queue, (clock, priority, serial, kind, payload))
    batches = {}
    by_id = {}
    for item in candidates:
        p = dict(item)
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
            if (fill['sip_timestamp'] < previous or fill['side'] != ('buy' if i % 2 == 0 else 'sell')
                    or fill['decision_ns'] < clock or fill['decision_ns'] > fill['sip_timestamp']):
                raise ValueError('Quote path has invalid event chronology')
            previous = fill['sip_timestamp']
        by_id[p['proposal_id']] = p
        batches.setdefault(clock, []).append(p)
    for clock in clocks:
        event(clock, 1, 'mark', None)
    for clock, batch in batches.items():
        event(clock, 2, 'decide', sorted(batch, key=lambda p: (-p['score'], p['proposal_id'])))
    active, reservations, decisions, marks = {}, {}, [], []
    completed, capture_complete = set(), True

    def equity(clock):
        return ledger.cash + sum(position['quantity'] * policy.multiplier *
            archive.mark(position['contract'], clock)['bid'] for position in ledger.positions.values())

    while queue:
        clock, _, _, kind, payload = heapq.heappop(queue)
        if clock > clocks[-1]:
            break
        if kind == 'mark':
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
                budget = min(ledger.cash - sum(reservations.values()), fraction * value)
                if budget <= 0:
                    decisions.append({'proposal_id': key, 'clock_ns': clock, 'status': 'no_cash'})
                    continue
                reservations[key] = budget
                active[key] = {'symbol': p['symbol'], 'entry_budget': budget}
                decisions.append({'proposal_id': key, 'clock_ns': clock, 'status': 'reserved', 'budget': budget})
                # Inspecting the simulated path here only schedules its market
                # events. Success/failure/return never affects acceptance above.
                path = p['path']
                capture_complete &= path['capture_complete']
                for fill in path['fills']:
                    event(fill['sip_timestamp'], 0, 'fill', (key, fill))
                if not path['fills']:
                    event(clock + policy.entry_deadline_ns, 0, 'unfilled', key)
                elif path['label_complete']:
                    end = path['label_end_ns']
                    if end < path['fills'][-1]['sip_timestamp']:
                        raise ValueError('Terminal label precedes a market fill')
                    event(end, 0, 'terminal', key)
        elif kind == 'fill':
            key, fill = payload
            p = by_id[key]
            if fill['side'] == 'buy':
                budget = reservations.pop(key)
                date = pd.Timestamp(fill['decision_ns'], unit='ns', tz='UTC').tz_convert('America/New_York').date()
                if not ledger.buy(key, p['symbol'], fill, equity=max(ledger.cash, budget),
                                  budget=budget, decision_date=date, roll_of=fill.get('roll_of')):
                    raise ValueError('Reserved portfolio purchase was unexpectedly rejected')
            else:
                reservations[key] = ledger.sell(key, fill)
        elif kind in ('terminal', 'unfilled'):
            if payload in ledger.positions:
                raise ValueError('Cannot release an unresolved position slot')
            reservations.pop(payload, None)
            active.pop(payload)
            completed.add(payload)
    ledger.reconcile()
    return {'cash': ledger.cash, 'reserved_cash': sum(reservations.values()),
            'open_positions': ledger.positions, 'active_proposals': active,
            'fills': ledger.events, 'decisions': decisions, 'marks': marks,
            'capture_complete': capture_complete,
            'complete': not active and capture_complete,
            'valuation_complete': all(m['status'] == 'observed' for m in marks),
            'completed_proposals': sorted(completed),
            'allocation_policy': {'capital': capital, 'slots': slots, 'fraction': fraction,
                'one_position_per_symbol_across_timeframes': True,
                'order': 'descending causal score, then ascending proposal_id',
                'unavailable_held_mark': 'pause new entries; continue observed exits',
                'fractional_paper': True}}
