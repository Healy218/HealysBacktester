"""Synthetic ETFE expiry/roll successor; preserves its option-prefix artifact.

This bounded continuation owns lifecycle mechanics, not real source admission,
ordinary new-entry scheduling, labels or whole-history execution acceptance.
"""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import math
from pathlib import Path

from .execution_ledger import OptionLedger, END, NY, canonical, cents, source_hash
from .purchase_policy_v2 import expiry_entry_gate, purchase_dte
from .vwap_reference import utc_time

SCHEMA = 'etfe-synthetic-expiry-ledger-v1'


def binding():
    return hashlib.sha256((source_hash() + Path(__file__).read_text()).encode()).hexdigest()


def positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def settlement_clock(trade_date, calendar, *, option=False):
    """Explicit complete dated settlement calendar, including transition overrides."""
    if calendar.get('evidence_kind') != 'synthetic':
        raise ValueError('Synthetic dated calendar required')
    days = calendar['business_dates']
    if days != sorted(set(days)) or trade_date not in days:
        return None
    lag = 1 if option or trade_date >= '2024-05-28' else 2
    overrides = calendar.get('equity_overrides', {})
    if not option and trade_date in overrides:
        due = overrides[trade_date]
        if due not in days or due <= trade_date:
            raise ValueError('Invalid dated settlement override')
    else:
        i = days.index(trade_date) + lag
        if i >= len(days):
            return None
        due = days[i]
    from datetime import datetime
    return datetime.combine(date.fromisoformat(due), datetime.min.time(), NY).replace(hour=9, minute=30).isoformat()


class ExpiryLedger(OptionLedger):
    def __init__(self, option_snapshot, lifecycle):
        prefix = OptionLedger.restore(option_snapshot)
        if lifecycle.get('evidence_kind') != 'synthetic' or prefix.clock is None:
            raise ValueError('Synthetic lifecycle and observed option prefix required')
        if prefix.outcome()['status'] == 'input_unresolved' or any(p['status'] == 'pending' for p in prefix.proposals.values()):
            raise ValueError('Unresolved prefix cannot be relabeled')
        for c in prefix.positions:
            if utc_time(prefix.clock) >= utc_time(prefix.fixture['contracts'][c]['expiry_close']) - timedelta(minutes=15):
                raise ValueError('Continue from a prefix before expiry cutoff')
        self.__dict__.update(deepcopy(prefix.__dict__))
        self.lifecycle = deepcopy(lifecycle)
        fee = lifecycle.get('exercise_fee', 0)
        if isinstance(fee, bool) or not isinstance(fee, (int, float)) or not math.isfinite(fee) or fee < 0:
            raise ValueError('Nonnegative finite exercise fee required')
        self.prefix_sha256 = hashlib.sha256(canonical(option_snapshot).encode()).hexdigest()
        self.prefix = deepcopy(option_snapshot)
        self.source = binding()
        self.deliveries = []
        self.stocks = {}  # lots keyed by original proposal; all shares purchased through exercise
        self.rolls = {}
        self.roll_counts = {pid: 0 for pid in self.proposals}
        self.strategy_off = []
        self.expired = []
        self.quote_ids = {}
        self.used_quotes = []
        self.cash_changes = []
        self.input_waits = {}
        self._event('lifecycle_continuation', prefix_sha256=self.prefix_sha256)

    def step(self, *args, **kwargs):
        raise ValueError('Use advance; ordinary entry scheduling is outside this component')

    def _problem(self, kind, reason, contract):
        item = dict(kind=kind, reason=reason, contract=contract)
        if item not in self.unresolved:
            self.unresolved.append(item)
            self._event(kind, reason=reason, contract=contract)

    def _terms(self, contract, now):
        terms = self.lifecycle['terms'].get(contract)
        if not terms:
            return None
        try:
            valid = (utc_time(terms['known_at']) <= now and utc_time(terms['effective_at']) <= now < utc_time(terms['ends_at'])
                     and positive(terms['strike']) and positive(terms['shares_per_contract'])
                     and float(terms['shares_per_contract']).is_integer()
                     and positive(terms['strike_cash_per_contract'])
                     and isinstance(terms['cash_per_contract'], (int, float))
                     and math.isfinite(terms['cash_per_contract']) and terms['cash_per_contract'] >= 0)
        except (KeyError, ValueError, TypeError):
            return None
        return terms if valid else None

    def _quote(self, symbol, now, quotes):
        q = quotes.get(symbol)
        session = self.lifecycle['stock_sessions'].get(symbol, {}).get(str(now.astimezone(NY).date()))
        if not q or not session or not utc_time(session[0]) <= now < utc_time(session[1]):
            return None
        try:
            stamp, known = utc_time(q['t']), utc_time(q['available_at'])
            valid = (q['feed'] == 'sip' and q['symbol'] == symbol and stamp <= known <= now
                     and 0 <= (now - stamp).total_seconds() <= 30
                     and all(positive(q[x]) for x in ('bid', 'ask', 'bid_size', 'ask_size', 'size_to_shares'))
                     and q['bid'] <= q['ask'] and q['id'])
        except (KeyError, TypeError, ValueError):
            return None
        if not valid:
            return None
        key = symbol + '|' + q['id']
        identity = canonical(q)
        if key in self.quote_ids and self.quote_ids[key] != identity:
            self._problem('input_unresolved', 'quote_identity_changed', symbol)
            return None
        self.quote_ids[key] = identity
        return dict(q, key=key, midpoint=(q['bid'] + q['ask']) / 2)

    def _due(self, now, *, option=False):
        return settlement_clock(str(now.astimezone(NY).date()), self.lifecycle['calendar'], option=option)

    def _change_cash(self, amount, reason, pid):
        self.cash += amount
        self.cash_changes.append(dict(cents=amount, reason=reason, proposal_id=pid))
        self._event('cash_change', cents=amount, reason=reason, proposal_id=pid)

    def _receivable(self, amount, due, contract, pid, reason):
        self.receivables.append(dict(cents=amount, due=due, contract=contract, proposal_id=pid,
                                     settled=False, reason=reason))
        if due is None:
            self._problem('input_unresolved', 'settlement_calendar_missing', contract)

    def roll_budget(self, pid):
        roll = self.rolls[pid]
        return sum(r['cents'] for r in self.receivables if r['proposal_id'] == pid
                   and r['contract'] == roll['old_contract'] and r['settled']
                   and r.get('reason') == 'option_sale')

    def available_cash(self, own_roll=None):
        reserve = sum(d['debit_cents'] for d in self.deliveries if not d['settled'])
        reserve += sum(self.roll_budget(pid) for pid, r in self.rolls.items()
                       if not r['cancelled'] and pid != own_roll)
        return self.cash - reserve

    def _settle(self, now):
        for r in self.receivables:
            if not r['settled'] and r['due'] and utc_time(r['due']) <= now:
                r['settled'] = True
                self._change_cash(r['cents'], 'receivable_settlement', r['proposal_id'])
        for d in self.deliveries:
            if d['settled'] or utc_time(d['due']) > now:
                continue
            self._change_cash(-d['debit_cents'] + d['credit_cents'], 'exercise_settlement', d['proposal_id'])
            d['settled'] = True
            if d['right'] == 'C':
                self.stocks[d['proposal_id']] = dict(symbol=d['symbol'], shares=d['shares'], mark=None,
                    intent_at=d['due'], origin_contract=d['contract'])
            else:
                remaining = d['shares']
                for lot in self.stocks.values():
                    if lot['symbol'] == d['symbol']:
                        q = min(remaining, lot['shares'])
                        lot['shares'] -= q
                        remaining -= q
                assert remaining == 0
            self._event('physical_delivery', **d)
        for pid in list(self.rolls):
            r = self.rolls[pid]
            pending = any(not x['settled'] for x in self.receivables if x['proposal_id'] == pid)
            if r['cancelled'] and r['old_contract'] not in self.positions and not pending:
                del self.rolls[pid]

    def _exercise(self, contract, now, reference):
        p = self.positions[contract]
        terms = self._terms(contract, now)
        base = self.fixture['contracts'][contract]
        close = utc_time(base['expiry_close'])
        valid = (reference and reference.get('kind') == 'official_exercise_reference'
                 and reference.get('contract') == contract and positive(reference.get('price')))
        if valid:
            valid = (utc_time(reference['reference_at']) == close
                     and close <= utc_time(reference['available_at']) <= now)
        if not terms or not valid:
            self._problem('input_unresolved', 'dated_exercise_reference_or_terms_missing', contract)
            return
        self.input_waits.pop(contract, None)
        if terms.get('exercise_basis') == 'standard_per_share' and terms['cash_per_contract'] == 0 and terms['shares_per_contract'] == base['multiplier'] and cents(terms['strike_cash_per_contract']) == cents(terms['strike'] * base['multiplier']):
            intrinsic = Decimal(str(reference['price'])) - Decimal(str(terms['strike']))
            if base['right'] == 'P':
                intrinsic = -intrinsic
        elif terms.get('exercise_basis') == 'official_intrinsic_per_share' and isinstance(reference.get('intrinsic_per_share'), (int, float)) and math.isfinite(reference['intrinsic_per_share']):
            intrinsic = Decimal(str(reference['intrinsic_per_share']))
        else:
            self._problem('input_unresolved', 'exercise_basis_unresolved', contract)
            return
        pid, quantity = p['proposal_id'], p['quantity']
        if intrinsic < Decimal('.01'):
            self.expired.append(dict(contract=contract, quantity=quantity, reason='nonexercise'))
            self._event('nonexercise', contract=contract, quantity=quantity, reference=reference)
            del self.positions[contract]
            if pid in self.rolls:
                self.rolls[pid]['cancelled'] = True
            return
        due = self._due(close)
        if due is None:
            self._problem('input_unresolved', 'exercise_settlement_calendar_missing', contract)
            return
        shares = int(quantity * terms['shares_per_contract'])
        strike_cash = cents(quantity * terms['strike_cash_per_contract'])
        deliverable_cash = cents(quantity * terms['cash_per_contract'])
        fee = cents(quantity * self.lifecycle.get('exercise_fee', 0))
        debit = strike_cash + fee if base['right'] == 'C' else deliverable_cash + fee
        credit = deliverable_cash if base['right'] == 'C' else strike_cash
        owned = sum(lot['shares'] for lot in self.stocks.values() if lot['symbol'] == base['symbol'])
        reserved = sum(d['shares'] for d in self.deliveries if d['symbol'] == base['symbol'] and d['right'] == 'P' and not d['settled'])
        if debit > self.available_cash() or base['right'] == 'P' and shares > owned - reserved:
            self._problem('funding_unresolved', 'exercise_cash_or_settled_shares_insufficient', contract)
            return
        d = dict(contract=contract, proposal_id=pid, symbol=base['symbol'], right=base['right'],
                 quantity=quantity, shares=shares, debit_cents=debit, credit_cents=credit,
                 exercise_fee_cents=fee, due=due, settled=False, mark=None)
        self.deliveries.append(d)
        self.expired.append(dict(contract=contract, quantity=quantity, reason='exercise'))
        self._event('exercise_reservation', **d, reference=reference)
        del self.positions[contract]
        if pid in self.rolls:
            self.rolls[pid]['cancelled'] = True

    def equity(self):
        if self.unresolved or any(p['mark'] is None for p in self.positions.values()):
            return None
        assets = self.cash / 100 + sum(r['cents'] / 100 for r in self.receivables if not r['settled'])
        assets += sum(p['quantity'] * self.fixture['contracts'][c]['multiplier'] * p['mark'] for c, p in self.positions.items())
        for lot in self.stocks.values():
            if lot['shares'] and lot['mark'] is None:
                return None
            assets += lot['shares'] * (lot['mark'] or 0)
        for d in self.deliveries:
            if d['settled']:
                continue
            if d['mark'] is None:
                return None
            assets += (d['credit_cents'] - d['debit_cents']) / 100
            assets += d['shares'] * d['mark'] * (1 if d['right'] == 'C' else -1)
        return assets

    def _select_roll(self, pid, now, quote):
        if not quote or self.lifecycle.get('selection_complete') is not True:
            return None
        original = self.proposals[pid]['proposal']
        spot, candidates = quote['midpoint'], []
        for contract, base in self.fixture['contracts'].items():
            terms = self._terms(contract, now)
            if not terms or base['symbol'] != original['symbol'] or base['right'] != original['right']:
                continue
            if utc_time(base['known_at']).astimezone(NY).date() >= now.astimezone(NY).date():
                continue
            gate = expiry_entry_gate(base['expiration_date'], now, target=original['target'], signal_qualifies=True,
                expiry_close=base['expiry_close'], weekly_eligible=base.get('weekly_eligible', False))
            if gate['entry_eligible'] and .85 * spot <= terms['strike'] <= 1.15 * spot:
                candidates.append((abs(purchase_dte(base['expiration_date'], now) - original['target']),
                                   base['expiration_date'], abs(terms['strike'] - spot), terms['strike'], contract))
        return min(candidates)[-1] if candidates else None

    def advance(self, at, *, bars=None, quotes=None, exercises=None, strategy_off=(), roll_signals=(), coverage=None):
        """Atomic observation: settlements→marks/intents→exits/exercise→rolls."""
        trial = deepcopy(self)
        trial._advance(at, bars or {}, quotes or {}, exercises or {}, strategy_off, roll_signals, coverage or {})
        trial._check()
        self.__dict__.update(trial.__dict__)

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
            fee, slip = gross * .001, gross * .0005
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
                original = self.proposals[pid]['proposal']
                chosen = self._select_roll(pid, now, stock_refs[original['symbol']])
                if self.lifecycle.get('selection_complete') is not True or stock_refs[original['symbol']] is None:
                    self.input_waits[pid] = 'roll_selection_inputs_missing'
                    if coverage.get(original['symbol']) is not True or self.lifecycle.get('selection_complete') is not True:
                        self.data_failure = True
                else:
                    self.input_waits.pop(pid, None)
                roll['attempt'] = dict(signal_at=self.clock, contract=chosen)
                self._event('roll_selection', proposal_id=pid, **roll['attempt'])
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
                    quantity = min(math.floor(max(0, budget) / (base['multiplier'] * ref['price'] * 1.0015)), self._capacity(ref))
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
        self.last_equity = self.equity()
        for pid in list(self.rolls):
            roll = self.rolls[pid]
            if roll['cancelled'] and roll['old_contract'] not in self.positions and not any(
                    not r['settled'] for r in self.receivables if r['proposal_id'] == pid):
                del self.rolls[pid]

    def _check(self):
        assert self.cash == self.prefix['state']['cash'] + sum(e['cents'] for e in self.cash_changes)
        assert self.cash >= 0 and self.available_cash() >= 0
        assert all(p['quantity'] > 0 and isinstance(p['quantity'], int) for p in self.positions.values())
        assert all(lot['shares'] >= 0 and isinstance(lot['shares'], int) for lot in self.stocks.values())
        assert all(0 <= n <= 60 for n in self.roll_counts.values())
        quantity, used = {}, {}
        for event in self.events:
            if event['kind'] != 'fill':
                continue
            c, q, ref = event['contract'], event['quantity'], event['reference']
            quantity[c] = quantity.get(c, 0) + (q if event['side'] == 'buy' else -q)
            used[ref['key']] = used.get(ref['key'], 0) + q
            assert quantity[c] >= 0 and used[ref['key']] <= math.floor(.01 * ref['volume'])
        for item in self.expired:
            quantity[item['contract']] -= item['quantity']
        assert {c: q for c, q in quantity.items() if q} == {c: p['quantity'] for c, p in self.positions.items()}
        assert used == self.used
        delivered = sum(d['shares'] * (1 if d['right'] == 'C' else -1) for d in self.deliveries if d['settled'])
        sold = sum(e['quantity'] for e in self.events if e['kind'] == 'stock_sale')
        assert delivered - sold == sum(lot['shares'] for lot in self.stocks.values())
        slots = self.slots()
        assert len(slots) <= 5
        assert len({self.proposals[pid]['proposal']['symbol'] for pid in slots}) == len(slots)

    def slots(self):
        return sorted({p['proposal_id'] for p in self.positions.values()} | set(self.rolls)
            | {pid for pid, lot in self.stocks.items() if lot['shares']}
            | {d['proposal_id'] for d in self.deliveries if not d['settled']}
            | {r['proposal_id'] for r in self.receivables if not r['settled']})

    def outcome(self, *, at_boundary=False):
        if any(x.get('kind') == 'funding_unresolved' for x in self.unresolved):
            status = 'funding_unresolved'
        elif self.unresolved or self.data_failure or self.input_waits:
            status = 'input_unresolved'
        elif self.slots():
            status = 'right_censored_end' if at_boundary else 'open'
        else:
            status = 'settled'
        return dict(status=status, cash_cents=self.cash, available_cash_cents=self.available_cash(),
            receivable_cents=sum(r['cents'] for r in self.receivables if not r['settled']),
            option_positions=deepcopy(self.positions), stocks=deepcopy(self.stocks),
            pending_deliveries=[deepcopy(d) for d in self.deliveries if not d['settled']],
            rolls=deepcopy(self.rolls), slots=self.slots(), unresolved=deepcopy(self.unresolved),
            pending_input_reasons=deepcopy(self.input_waits),
            last_processed_at=self.clock, training_admitted=False)

    def snapshot(self):
        import json
        return dict(schema=SCHEMA, state=json.loads(canonical(self.__dict__)))

    @classmethod
    def restore(cls, snapshot):
        if snapshot['schema'] != SCHEMA or snapshot['state']['source'] != binding():
            raise ValueError('Lifecycle schema/source mismatch')
        obj = cls(snapshot['state']['prefix'], snapshot['state']['lifecycle'])
        if obj.prefix_sha256 != snapshot['state']['prefix_sha256']:
            raise ValueError('Prefix identity mismatch')
        obj.__dict__.update(deepcopy(snapshot['state']))
        obj._check()
        return obj
