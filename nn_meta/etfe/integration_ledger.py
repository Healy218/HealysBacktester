"""Synthetic shared-ledger integration and deterministic observation scheduler.

The lifecycle event phase below is a versioned successor of expiry_ledger._advance
with parameterized costs and automatic roll cadence. Predecessors are intact.
"""
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
import math
from pathlib import Path

from .execution_ledger import OptionLedger, END, NY, canonical, cents
from .expiry_ledger import ExpiryLedger, binding as expiry_binding, settlement_clock
from .purchase_policy_v2 import expiry_entry_gate, purchase_dte
from .vwap_reference import utc_time

SCHEMA = 'etfe-synthetic-shared-scheduler-v1'
BASELINE = dict(cost_multiplier=1, lag_seconds=1, participation=.01,
                min_volume=1, min_count=1, remove_every_tenth=False,
                remove_edge_blocks=[], exercise_fee=0)


def binding():
    return hashlib.sha256((expiry_binding() + Path(__file__).read_text()).encode()).hexdigest()


def stress_profiles():
    profiles = {'baseline': deepcopy(BASELINE)}
    for field, values in [('cost_multiplier', [2, 3]), ('lag_seconds', [5, 30, 60]),
                          ('participation', [.005, .001]), ('min_volume', [10, 100]),
                          ('min_count', [2, 5]), ('exercise_fee', [5])]:
        for value in values:
            profiles[f'{field}-{value}'] = dict(deepcopy(BASELINE), **{field: value})
    profiles['remove_every_tenth'] = dict(deepcopy(BASELINE), remove_every_tenth=True)
    for side in ('first', 'last'):
        for block in range(6):
            profiles[f'remove_{side}_{block}'] = dict(deepcopy(BASELINE), remove_edge_blocks=[[side, block]])
    profiles['combined'] = dict(cost_multiplier=3, lag_seconds=60, participation=.001,
        min_volume=100, min_count=5, exercise_fee=5, remove_every_tenth=True,
        remove_edge_blocks=[[side, block] for side in ('first','last') for block in range(6)])
    return profiles


def stressed_bars(base, bars, policy):
    """Fixed chronological contract/session bar removal; never outcome selected."""
    result = {}
    for c, rows in bars.items():
        out = []
        # Removal ranks are within contract/session, counting valid activity bars.
        ranks = {}
        for bar in sorted(rows, key=lambda b: utc_time(b['t'])):
            start = utc_time(bar['t'])
            day = str(start.astimezone(NY).date())
            session = base['sessions'][c].get(day)
            if session is None:
                continue
            opening, closing = map(utc_time, session)
            if not opening <= start < closing:
                continue
            try:
                eligible = all(not isinstance(bar[k], bool) and math.isfinite(bar[k]) and bar[k] > 0 for k in ('vw','v','n'))
            except (KeyError, TypeError):
                eligible = False
            if eligible:
                ranks[day] = ranks.get(day, 0) + 1
            removed = eligible and policy['remove_every_tenth'] and ranks[day] % 10 == 0
            for side, block in policy['remove_edge_blocks']:
                anchor = opening + timedelta(minutes=5 * block) if side == 'first' else closing - timedelta(minutes=30 - 5 * block)
                removed = removed or anchor <= start < anchor + timedelta(minutes=5)
            if removed:
                continue
            row = deepcopy(bar)
            row['available_at'] = max(start + timedelta(seconds=60 + policy['lag_seconds']),
                                       utc_time(bar.get('available_at', start))).isoformat()
            out.append(row)
        result[c] = out
    return result


class SharedLedger(ExpiryLedger):
    def __init__(self, base, lifecycle, start, policy=None):
        policy = dict(deepcopy(BASELINE), **(policy or {}))
        if policy not in stress_profiles().values():
            raise ValueError('Use one of the declared finite stress profiles')
        initial = OptionLedger(base)
        initial.step(utc_time(start) - timedelta(microseconds=1))
        lifecycle = dict(deepcopy(lifecycle), exercise_fee=policy['exercise_fee'])
        super().__init__(initial.snapshot(), lifecycle)
        self.start_at = utc_time(start).isoformat()
        self.policy = policy
        self.source = binding()
        self.horizons = {}
        self.initial_lifecycle = deepcopy(lifecycle)

    def _capacity(self, ref):
        return max(0, math.floor(self.policy['participation'] * ref['volume']) - self.used.get(ref['key'], 0))

    def _reference(self, contract, now, bars):
        ref, reason = super()._reference(contract, now, bars)
        if ref and (ref['volume'] < self.policy['min_volume'] or ref['trade_count'] < self.policy['min_count']):
            return None, 'activity_below_stress_minimum'
        return ref, reason

    def _fill(self, side, contract, quantity, ref, proposal_id):
        gross = float(quantity * self.fixture['contracts'][contract]['multiplier'] * ref['price'])
        fee, slip = gross * .001 * self.policy['cost_multiplier'], gross * .0005 * self.policy['cost_multiplier']
        raw = gross + fee + slip if side == 'buy' else gross - fee - slip
        amount = cents(raw)
        self.used[ref['key']] = self.used.get(ref['key'], 0) + quantity
        self._event('fill', side=side, contract=contract, proposal_id=proposal_id,
            quantity=quantity, reference=ref, gross=gross, fee=fee, slippage=slip,
            cash_cents=amount, rounding_residual=amount / 100 - raw)
        return amount

    def _exercise(self, contract, now, reference):
        if reference is None:
            self.input_waits[contract] = 'official_exercise_reference_pending'
            return
        super()._exercise(contract, now, reference)

    def _selection_inputs_known(self, pid, now, quote):
        if quote is None or self.lifecycle.get('selection_complete') is not True:
            return False
        p = self.proposals[pid]['proposal']
        for c, base in self.fixture['contracts'].items():
            if base['symbol']==p['symbol'] and base['right']==p['right'] and 0 <= purchase_dte(base['expiration_date'],now) <= 5:
                if utc_time(base['known_at']).astimezone(NY).date() < now.astimezone(NY).date() and self._terms(c,now) is None:
                    return False
        return True

    def _begin_roll(self, pid, now, stock_refs, coverage):
        p = self.proposals[pid]['proposal']
        known = self._selection_inputs_known(pid, now, stock_refs[p['symbol']])
        chosen = self._select_roll(pid, now, stock_refs[p['symbol']]) if known else None
        if not known:
            self.input_waits[pid] = 'roll_selection_inputs_missing'
            if coverage.get(p['symbol']) is not True:
                self.data_failure = True
        else:
            self.input_waits.pop(pid, None)
        self.rolls[pid]['attempt'] = dict(signal_at=self.clock,contract=chosen)
        self._event('roll_selection',proposal_id=pid,**self.rolls[pid]['attempt'])

    def advance(self, at, *, entries=(), bars=None, quotes=None, exercises=None,
                strategy_off=(), roll_signals=(), coverage=None):
        trial = deepcopy(self)
        trial._advance(at, bars or {}, quotes or {}, exercises or {}, strategy_off, roll_signals, coverage or {})
        trial._entries(entries, bars or {}, quotes or {}, coverage or {})
        trial.last_equity = trial.equity()
        for pid, record in trial.proposals.items():
            if pid not in trial.slots() and record['status'] != 'pending':
                trial.horizons.setdefault(pid, trial.clock)
        trial._check()
        self.__dict__.update(trial.__dict__)

    def _entries(self, entries, bars, quotes, coverage):
        now = utc_time(self.clock)
        for p in entries:
            p = deepcopy(p)
            if p['id'] in self.proposals:
                raise ValueError('Duplicate proposal identity')
            if utc_time(p['signal_at']) != now or p['symbol'] not in ('SPY','QQQ','VOO') or p['right'] not in ('C','P'):
                raise ValueError('Proposal must register on its signal clock with scoped identity')
            self._tie(p)
            self.proposals[p['id']] = dict(proposal=p, status='pending', attempts=[])
            q = self._quote(p['symbol'], now, quotes)
            known = self._selection_inputs_known(p['id'], now, q)
            selected = self._select_roll(p['id'], now, q) if known else None
            reason = 'selected' if selected else 'no_eligible_contract'
            if not known:
                reason = 'selection_input_unresolved'
            self.proposals[p['id']].update(selected_contract=selected, selection_reason=reason,
                window_complete=coverage.get(p['symbol']) is True)
            self.roll_counts[p['id']] = 0
            self._event('entry_selection', proposal_id=p['id'], contract=selected, reason=reason)
        for pid, record in sorted(self.proposals.items(), key=lambda x: self._tie(x[1]['proposal'])):
            if record['status'] != 'pending':
                continue
            p = record['proposal']
            signal = utc_time(p['signal_at'])
            if now < signal + timedelta(seconds=1):
                continue
            c = record['selected_contract']
            reason = record['selection_reason']
            if c:
                record['window_complete'] &= coverage.get(c) is True
            if c and now <= signal + timedelta(seconds=60):
                base = self.fixture['contracts'][c]
                ref, reason = self._reference(c, now, bars.get(c, []))
                gate = expiry_entry_gate(base['expiration_date'], now, target=p['target'], signal_qualifies=p['qualifies'],
                    expiry_close=base['expiry_close'], weekly_eligible=base.get('weekly_eligible',False))
                equity = self.equity()
                if not gate['entry_eligible']:
                    reason = gate['reason']
                elif pid in self.strategy_off:
                    reason = 'strategy_off'
                elif self._terms(c, now) is None or equity is None or self.input_waits:
                    reason = 'valuation_or_terms_unresolved'
                elif len(self.slots()) >= 5 or any(self.proposals[other]['proposal']['symbol'] == p['symbol'] for other in self.slots()):
                    reason = 'slot_or_underlying_occupied'
                elif ref:
                    budget = max(0, min(self.available_cash() / 100, .1 * equity))
                    unit = base['multiplier'] * ref['price'] * (1 + .0015 * self.policy['cost_multiplier'])
                    quantity = min(math.floor(budget / unit), self._capacity(ref))
                    reason = 'size_ineligible'
                    if quantity:
                        amount = self._fill('buy', c, quantity, ref, pid)
                        self._change_cash(-amount, 'ordinary_purchase', pid)
                        self.positions[c] = dict(quantity=quantity, entry_vwap=ref['price'], mark=ref['price'],
                            last_mark_audit_only=ref['price'], exit_intent=None, proposal_id=pid)
                        record['status'] = 'filled'
                        reason = 'filled'
            record['attempts'].append(dict(at=self.clock, reason=reason))
            self._event('entry_attempt', proposal_id=pid, reason=reason)
            invalid = {'selection_input_unresolved','valuation_or_terms_unresolved','newest_bar_invalid',
                       'ambiguous_revision','revision_after_use','session_unavailable'}
            if reason in invalid:
                record['window_complete'] = False
            if record['status'] == 'pending' and now >= signal + timedelta(seconds=60):
                record['status'] = 'observed_unfilled' if record['window_complete'] else 'input_unresolved'

    def _check(self):
        super()._check()
        for e in self.events:
            if e['kind'] == 'fill':
                ref = e['reference']
                assert self.used[ref['key']] <= math.floor(self.policy['participation'] * ref['volume'])

    def path_reports(self, *, at_boundary=False):
        result = {}
        for pid, record in self.proposals.items():
            symbol = record['proposal']['symbol']
            contracts = {e['contract'] for e in self.events if e['kind']=='fill' and e['proposal_id']==pid}
            issues = [x for x in self.unresolved if x['contract'] in contracts or x['contract']==symbol]
            if any(x.get('kind')=='funding_unresolved' for x in issues):
                status='funding_unresolved'
            elif issues or self.data_failure or record['status']=='input_unresolved' or any(k in contracts or k==pid for k in self.input_waits):
                status='input_unresolved'
            elif pid in self.slots() or record['status']=='pending':
                status='right_censored_end' if at_boundary else 'open'
            else:
                status='settled' if record['status']=='filled' else record['status']
            changes = [x['cents'] for x in self.cash_changes if x['proposal_id']==pid]
            result[pid] = dict(status=status, terminal_at=self.horizons.get(pid) if status in ('settled','observed_unfilled') else None,
                known_cashflow_cents=sum(changes), synthetic_pnl_cents=sum(changes) if status=='settled' else None,
                target=None, training_admitted=False)
        return result

    def outcome(self, *, at_boundary=False):
        out=super().outcome(at_boundary=at_boundary)
        paths=self.path_reports(at_boundary=at_boundary)
        states={p['status'] for p in paths.values()}
        for status in ('funding_unresolved','input_unresolved','right_censored_end','open'):
            if status in states:
                out['status']=status
                break
        return dict(out,paths=paths)

    def snapshot(self):
        return dict(schema=SCHEMA, state=json.loads(canonical(self.__dict__)))

    @classmethod
    def restore(cls, snapshot):
        state=snapshot['state']
        if snapshot['schema']!=SCHEMA or state['source']!=binding():
            raise ValueError('Shared ledger source/schema mismatch')
        obj=cls(state['fixture'],state['initial_lifecycle'],state['start_at'],state['policy'])
        obj.__dict__.update(deepcopy(state));obj._check()
        return obj

    def _advance(self, at, bars, quotes, exercises, strategy_off, roll_signals, coverage):
        now = utc_time(at)
        if now >= END or now <= utc_time(self.clock):
            raise ValueError('Increasing pre-boundary clock required')
        self.clock = now.isoformat()
        self._settle(now)
        self.strategy_off = sorted(set(self.strategy_off) | set(strategy_off))
        for pid, roll in self.rolls.items():
            if pid in self.strategy_off:
                roll['cancelled'] = True
                self.input_waits.pop(pid, None)
        stock_refs = {s: self._quote(s, now, quotes) for s in ('SPY', 'QQQ', 'VOO')}
        refs = {}
        for c, p in self.positions.items():
            ref, reason = self._reference(c, now, bars.get(c, []))
            refs[c] = ref
            p['mark'] = ref['price'] if ref else None
            base = self.fixture['contracts'][c]
            close = utc_time(base['expiry_close'])
            pid = p['proposal_id']
            if now < close and ref is None:
                self.valuation_gaps.append(dict(at=self.clock, contract=c, reason=reason))
                if coverage.get(c) is not True or reason in ('newest_bar_invalid', 'ambiguous_revision', 'revision_after_use'):
                    self.data_failure = True
            if ref and ref['price'] <= .875 * p['entry_vwap']:
                p['exit_intent'] = p['exit_intent'] or 'premium_stop'
                if pid in self.rolls:
                    self.rolls[pid]['cancelled'] = True
            if pid in self.strategy_off:
                p['exit_intent'] = p['exit_intent'] or 'strategy_exit'
            if close - timedelta(minutes=15) <= now < close and not p['exit_intent']:
                quote, terms = stock_refs[base['symbol']], self._terms(c, now)
                if quote is None or terms is None:
                    self.input_waits[c] = 'expiry_classification_unresolved'
                    if coverage.get(base['symbol']) is not True or terms is None:
                        self.data_failure = True
                    self._event('expiry_classification_unresolved', contract=c)
                    continue
                self.input_waits.pop(c, None)
                deliverable_value = quote['midpoint'] * terms['shares_per_contract'] + terms['cash_per_contract']
                itm = deliverable_value > terms['strike_cash_per_contract'] if base['right'] == 'C' else deliverable_value < terms['strike_cash_per_contract']
                p['exit_intent'] = 'expiry_itm' if itm else 'expiry_otm'
                self._event('expiry_classification', contract=c, itm=itm, quote=quote)
                if not itm and pid not in self.strategy_off and self.roll_counts[pid] < 60:
                    self.rolls[pid] = dict(old_contract=c, cancelled=False, attempt=None, attempts=[])
        for lot in self.stocks.values():
            quote = stock_refs[lot['symbol']]
            lot['mark'] = quote['midpoint'] if quote else None
            if lot['shares'] and not quote:
                self.valuation_gaps.append(dict(at=self.clock, symbol=lot['symbol'], reason='stock_mark_missing'))
                if coverage.get(lot['symbol']) is not True:
                    self.data_failure = True
        for d in self.deliveries:
            q = stock_refs[d['symbol']]
            d['mark'] = q['midpoint'] if q else None
        order = lambda pid: self._tie(self.proposals[pid]['proposal'])
        for c in sorted(list(self.positions), key=lambda c: order(self.positions[c]['proposal_id'])):
            p, base, ref = self.positions[c], self.fixture['contracts'][c], refs[c]
            if now >= utc_time(base['expiry_close']):
                self._exercise(c, now, exercises.get(c))
                continue
            if not p['exit_intent'] or ref is None:
                continue
            q = min(p['quantity'], self._capacity(ref))
            if not q:
                continue
            amount = self._fill('sell', c, q, ref, p['proposal_id'])
            self._receivable(amount, self._due(now, option=True), c, p['proposal_id'], 'option_sale')
            p['quantity'] -= q
            if p['quantity'] == 0:
                del self.positions[c]
        for pid, lot in sorted(self.stocks.items(), key=lambda item: order(item[0])):
            q = stock_refs[lot['symbol']]
            if not lot['shares'] or q is None or q['key'] in self.used_quotes or now < utc_time(lot['intent_at']) + timedelta(seconds=1):
                continue
            reserved = sum(d['shares'] for d in self.deliveries if d['symbol'] == lot['symbol'] and d['right'] == 'P' and not d['settled'])
            quantity = min(max(0, lot['shares'] - reserved), math.floor(q['bid_size'] * q['size_to_shares']))
            if not quantity:
                continue
            gross = quantity * q['bid']
            fee, slip = gross * .001 * self.policy['cost_multiplier'], gross * .0005 * self.policy['cost_multiplier']
            raw = gross - fee - slip
            amount = cents(raw)
            self._receivable(amount, self._due(now), lot['origin_contract'], pid, 'stock_sale')
            lot['shares'] -= quantity
            self.used_quotes.append(q['key'])
            self._event('stock_sale', proposal_id=pid, symbol=lot['symbol'], quantity=quantity,
                quote=q, gross=gross, fee=fee, slippage=slip, cash_cents=amount, rounding_residual=amount / 100 - raw)
        for pid, roll in sorted(list(self.rolls.items()), key=lambda item: order(item[0])):
            if roll['cancelled'] or roll['old_contract'] in self.positions or self.unresolved:
                continue
            pending = any(not r['settled'] for r in self.receivables if r['proposal_id'] == pid)
            if pending:
                continue
            if pid in roll_signals and (roll['attempt'] is None or now > utc_time(roll['attempt']['signal_at']) + timedelta(seconds=60)):
                self._begin_roll(pid, now, stock_refs, coverage)
            attempt = roll['attempt']
            if attempt is None:
                continue
            c = attempt['contract']
            reason = ('selection_unresolved' if pid in self.input_waits else 'no_eligible_contract') if c is None else 'outside_roll_window'
            if c and utc_time(attempt['signal_at']) + timedelta(seconds=1) <= now <= utc_time(attempt['signal_at']) + timedelta(seconds=60):
                base = self.fixture['contracts'][c]
                gate = expiry_entry_gate(base['expiration_date'], now, target=self.proposals[pid]['proposal']['target'],
                    signal_qualifies=pid not in self.strategy_off, expiry_close=base['expiry_close'], weekly_eligible=base.get('weekly_eligible', False))
                ref, reason = self._reference(c, now, bars.get(c, []))
                equity = self.equity()
                if not gate['entry_eligible']:
                    reason = gate['reason']
                elif self._terms(c, now) is None or equity is None:
                    reason = 'valuation_or_terms_unresolved'
                elif ref:
                    budget = min(self.roll_budget(pid), self.available_cash(own_roll=pid), .1 * equity * 100) / 100
                    quantity = min(math.floor(max(0, budget) / (base['multiplier'] * ref['price'] * (1 + .0015 * self.policy['cost_multiplier']))), self._capacity(ref))
                    reason = 'size_ineligible'
                    if quantity:
                        amount = self._fill('buy', c, quantity, ref, pid)
                        self._change_cash(-amount, 'roll_purchase', pid)
                        self.positions[c] = dict(quantity=quantity, entry_vwap=ref['price'], mark=ref['price'],
                            last_mark_audit_only=ref['price'], exit_intent=None, proposal_id=pid)
                        self.roll_counts[pid] += 1
                        reason = 'filled'
                        del self.rolls[pid]
            record = dict(at=self.clock, reason=reason, contract=c)
            roll['attempts'].append(record)
            self._event('roll_attempt', proposal_id=pid, **record)
            # Preserve the old attempt's inclusive final second, then open the
            # next regular observation's window without skipping a minute.
            if pid in self.rolls and pid in roll_signals and now == utc_time(attempt['signal_at']) + timedelta(seconds=60):
                self._begin_roll(pid, now, stock_refs, coverage)
        self.last_equity = self.equity()
        for pid in list(self.rolls):
            roll = self.rolls[pid]
            if roll['cancelled'] and roll['old_contract'] not in self.positions and not any(
                    not r['settled'] for r in self.receivables if r['proposal_id'] == pid):
                del self.rolls[pid]


class Scheduler:
    """Complete clocks within one declared synthetic fixture interval.

    The immutable tape supplies capture-coverage assertions, not inferred from
    populated rows. Risk/entry/roll clocks and settlement events are generated.
    A short fixture end is reported as open, never a fixed-boundary censor.
    """
    def __init__(self, tape, policy=None):
        self.tape = deepcopy(tape)
        if tape.get('evidence_kind') != 'synthetic':
            raise ValueError('Real tapes need independent source admission')
        self.policy = dict(deepcopy(BASELINE), **(policy or {}))
        start, end = utc_time(tape['start']), utc_time(tape['end'])
        if not start < end <= END:
            raise ValueError('Invalid bounded observation interval')
        self.ledger = SharedLedger(tape['base'], tape['lifecycle'], start, self.policy)
        self.bars = stressed_bars(tape['base'], tape.get('bars', {}), self.policy)
        self.cursor = 0
        self.tape_sha256 = hashlib.sha256(canonical(tape).encode()).hexdigest()
        times = {start, end - timedelta(microseconds=1)}
        self.regular = set()
        for sessions in tape['lifecycle']['stock_sessions'].values():
            for pair in sessions.values():
                opening, closing = map(utc_time, pair)
                t = opening
                while t <= closing:
                    if start <= t < end:
                        self.regular.add(t.isoformat())
                        times.add(t)
                        times.add(t + timedelta(seconds=1))
                        times.add(t + timedelta(seconds=self.policy['lag_seconds']))
                    t += timedelta(minutes=1)
        for sessions in tape['base']['sessions'].values():
            for pair in sessions.values():
                opening, closing = map(utc_time, pair)
                t = opening + timedelta(minutes=1)
                while t <= closing:
                    times.add(t + timedelta(seconds=self.policy['lag_seconds']))
                    t += timedelta(minutes=1)
        ids = set()
        for p in tape['proposals']:
            signal = utc_time(p['signal_at'])
            if p['id'] in ids or not start <= signal < end:
                raise ValueError('Duplicate or out-of-interval proposal')
            ids.add(p['id'])
            for second in range(61):
                times.add(signal + timedelta(seconds=second))
        for c, rows in self.bars.items():
            times.update(utc_time(b['available_at']) for b in rows)
        for rows in tape.get('quotes', {}).values():
            times.update(utc_time(q['available_at']) for q in rows)
        for rows in tape.get('exercises', {}).values():
            times.update(utc_time(r['available_at']) for r in rows)
        for base in tape['base']['contracts'].values():
            close = utc_time(base['expiry_close'])
            times.update([close - timedelta(minutes=15), close])
        for change in tape.get('strategy_exits', []):
            times.add(utc_time(change['at']))
        calendar = tape['lifecycle']['calendar']
        for day in calendar['business_dates']:
            for option in (True, False):
                due = settlement_clock(day, calendar, option=option)
                if due:
                    times.add(utc_time(due))
                    times.add(utc_time(due) + timedelta(seconds=1))
        self.times = sorted(t.isoformat() for t in times if start <= t < end)

    def _latest(self, rows, now, *, timestamp):
        known = [r for r in rows if utc_time(r['available_at']) <= now]
        if not known:
            return None
        latest = max(utc_time(r[timestamp]) for r in known)
        selected = [r for r in known if utc_time(r[timestamp]) == latest]
        if len({canonical(r) for r in selected}) != 1:
            raise ValueError('Ambiguous simultaneous reference revisions')
        return selected[0]

    def run(self, max_events=None):
        if max_events is not None and max_events < 1:
            raise ValueError('Positive event budget required')
        limit = len(self.times) if max_events is None else min(len(self.times), self.cursor + max_events)
        while self.cursor < limit:
            at = self.times[self.cursor]
            now = utc_time(at)
            quotes = {s: self._latest(rows, now, timestamp='t') for s, rows in self.tape.get('quotes', {}).items()}
            exercises = {c: self._latest(rows, now, timestamp='reference_at') for c, rows in self.tape.get('exercises', {}).items()}
            entries = [p for p in self.tape['proposals'] if utc_time(p['signal_at']) == now]
            exits = [e['proposal_id'] for e in self.tape.get('strategy_exits', []) if utc_time(e['at']) == now]
            roll_signals = list(self.ledger.rolls) if at in self.regular else []
            self.ledger.advance(at, entries=entries, bars=self.bars, quotes=quotes,
                exercises=exercises, strategy_off=exits, roll_signals=roll_signals,
                coverage=self.tape.get('coverage', {}))
            self.cursor += 1
        return self.report()

    def report(self):
        complete = self.cursor == len(self.times)
        boundary = complete and utc_time(self.tape['end']) == END
        paths = self.ledger.path_reports(at_boundary=boundary)
        counts = {}
        for p in paths.values():
            counts[p['status']] = counts.get(p['status'], 0) + 1
        return dict(complete=complete, events_processed=self.cursor, events_total=len(self.times),
            proposal_count=len(self.tape['proposals']), registered_count=len(paths), census=counts,
            paths=paths, cash_cents=self.ledger.cash, training_admitted=False,
            fixed_end_reached=boundary, revision_sensitivity='unmeasured')

    def snapshot(self):
        return dict(schema=SCHEMA, source=binding(), tape_sha256=self.tape_sha256,
                    policy=self.policy, cursor=self.cursor, ledger=self.ledger.snapshot())

    @classmethod
    def restore(cls, tape, snapshot):
        if snapshot['schema'] != SCHEMA or snapshot['source'] != binding():
            raise ValueError('Scheduler schema/source mismatch')
        obj = cls(tape, snapshot['policy'])
        if obj.tape_sha256 != snapshot['tape_sha256']:
            raise ValueError('Scheduler input identity mismatch')
        obj.ledger = SharedLedger.restore(snapshot['ledger'])
        obj.cursor = snapshot['cursor']
        if not isinstance(obj.cursor, int) or not 0 <= obj.cursor <= len(obj.times):
            raise ValueError('Invalid scheduler cursor')
        expected = obj.times[obj.cursor-1] if obj.cursor else (utc_time(tape['start']) - timedelta(microseconds=1)).isoformat()
        if obj.ledger.clock != expected:
            raise ValueError('Cursor/ledger clock mismatch')
        return obj
