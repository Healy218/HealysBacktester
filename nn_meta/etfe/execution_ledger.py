"""Bounded ETFE option ledger. Synthetic mechanics only; no input admission.

The caller supplies the observation clock, dated sessions and settlement dates.
Rolls and physical expiry deliberately stop unresolved in this version.
"""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_EVEN
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from .purchase_policy_v2 import expiry_entry_gate
from .vwap_reference import reference_from_bar, utc_time

SCHEMA = 'etfe-synthetic-option-ledger-v1'
NY = ZoneInfo('America/New_York')
END = utc_time('2026-10-03T04:00:00Z')


def cents(value):
    return int(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_EVEN) * 100)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def source_hash():
    root = Path(__file__).resolve().parents[2]
    paths = ['nn_meta/etfe/execution_ledger.py', 'nn_meta/etfe/vwap_reference.py',
             'nn_meta/etfe/purchase_policy_v2.py', 'docs/specs/ETFE_SCOPE_0DTE_20261004.json']
    return hashlib.sha256(b''.join((root / p).read_bytes() for p in paths)).hexdigest()


class OptionLedger:
    """One portfolio with shared cash/capacity; all money balances in cents.

    `fixture` is explicitly synthetic, not a source-admission escape hatch.
    Sessions are keyed by contract and NY date. Settlement maps trade NY dates
    to the NEXT business day's 09:30 NY clock; caller owns holiday coverage.
    Missing map entries preserve unresolved receivables rather than instant cash.
    """

    def __init__(self, fixture):
        if fixture.get('evidence_kind') != 'synthetic':
            raise ValueError('Real execution requires a separately validated integration')
        self.fixture = deepcopy(fixture)
        self.source = source_hash()
        self.cash = 10_000_000
        self.positions = {}
        self.proposals = {}
        self.receivables = []
        self.used = {}
        self.references = {}
        self.events = []
        self.clock = None
        self.valuation_gaps = []
        self.unresolved = []
        self.data_failure = False
        self.last_equity = 100_000.0
        for contract, terms in self.fixture['contracts'].items():
            if terms['symbol'] not in ('SPY', 'QQQ', 'VOO') or terms['right'] not in ('C', 'P'):
                raise ValueError('Unsupported symbol/right')
            if not math.isfinite(terms['multiplier']) or terms['multiplier'] <= 0:
                raise ValueError('Positive dated monetary multiplier required')
            close = utc_time(terms['expiry_close'])
            if str(close.astimezone(NY).date()) != terms['expiration_date']:
                raise ValueError('Expiry date mismatch')
            utc_time(terms['known_at'])
            for day, session in self.fixture['sessions'][contract].items():
                opening, closing = map(utc_time, session)
                if opening >= closing or any(str(t.astimezone(NY).date()) != day for t in (opening, closing)):
                    raise ValueError('Invalid dated session')
        for day, stamp in self.fixture['settlements'].items():
            local = utc_time(stamp).astimezone(NY)
            if str(local.date()) <= day or (local.hour, local.minute, local.second, local.microsecond) != (9, 30, 0, 0):
                raise ValueError('Settlement must be a later dated 09:30 NY clock')

    def _event(self, kind, **fields):
        self.events.append(dict(fields, at=self.clock, kind=kind))

    def _issue(self, reason, contract):
        item = dict(reason=reason, contract=contract)
        if item not in self.unresolved:
            self.unresolved.append(item)
            self._event('input_unresolved', **item)

    def _session(self, contract, now):
        pair = self.fixture['sessions'][contract].get(str(now.astimezone(NY).date()))
        return tuple(map(utc_time, pair)) if pair else None

    def _reference(self, contract, now, bars):
        session = self._session(contract, now)
        if session is None or not session[0] <= now < min(session[1], utc_time(self.fixture['contracts'][contract]['expiry_close'])):
            return None, 'session_unavailable'
        known = []
        for bar in bars:
            start = utc_time(bar['t'])
            available = max(start + timedelta(seconds=61), utc_time(bar.get('available_at', start + timedelta(seconds=61))))
            if session[0] <= start and start + timedelta(minutes=1) <= session[1] and available <= now:
                known.append((start, available, bar))
        if not known:
            return None, 'reference_missing'
        newest = max(x[0] for x in known)
        selected = [x for x in known if x[0] == newest]
        try:
            if len({canonical(x[2]) for x in selected}) != 1:
                return None, 'ambiguous_revision'
        except ValueError:
            return None, 'newest_bar_invalid'
        _, available, bar = selected[0]
        try:
            ref = reference_from_bar(bar, as_of=now, available_at=available)
        except ValueError:
            return None, 'newest_bar_invalid'
        if ref is None:
            return None, 'reference_stale'
        key = contract + '|' + ref['bar_start']
        identity = canonical({k: ref[k] for k in ('price', 'volume', 'trade_count', 'available_at')})
        if key in self.references and self.references[key] != identity:
            return None, 'revision_after_use'
        self.references[key] = identity
        ref['key'] = key
        return ref, None

    def _capacity(self, ref):
        return max(0, math.floor(.01 * ref['volume']) - self.used.get(ref['key'], 0))

    @staticmethod
    def _tie(proposal):
        return (utc_time(proposal['signal_at']), proposal['symbol'], proposal['variant'],
                proposal['right'], proposal['target'], proposal['id'])

    def _fill(self, side, contract, quantity, ref, proposal_id):
        gross = float(quantity * self.fixture['contracts'][contract]['multiplier'] * ref['price'])
        fee, slippage = gross * .001, gross * .0005
        raw = gross + fee + slippage if side == 'buy' else gross - fee - slippage
        amount = cents(raw)
        self.used[ref['key']] = self.used.get(ref['key'], 0) + quantity
        self._event('fill', side=side, contract=contract, proposal_id=proposal_id,
                    quantity=quantity, reference=ref, gross=gross, fee=fee,
                    slippage=slippage, cash_cents=amount, rounding_residual=amount / 100 - raw)
        return amount

    def step(self, at, *, bars=None, entries=(), exits=(), coverage=None):
        """Process one strictly increasing observation, settle→mark→exit→entry.

        Bars are a caller-provided snapshot, never forward-filled. Coverage maps
        contract to a boolean for THIS observation, not an entire entry window.
        Repeated entries retry the same immutable proposal until its deadline.
        """
        trial = deepcopy(self)
        trial._step(at, bars=bars, entries=entries, exits=exits, coverage=coverage)
        self.__dict__.update(trial.__dict__)

    def _step(self, at, *, bars, entries, exits, coverage):
        now = utc_time(at)
        if now >= END or self.clock is not None and now <= utc_time(self.clock):
            raise ValueError('Strictly increasing pre-boundary observations required')
        # Reject inconsistent proposals before mutating the ledger.
        prepared = []
        seen = set()
        for source in entries:
            p = deepcopy(source)
            terms = self.fixture['contracts'][p['contract']]
            p.update(symbol=terms['symbol'], right=terms['right'])
            self._tie(p)
            if p['id'] in seen:
                raise ValueError('Duplicate proposal in observation')
            seen.add(p['id'])
            if p['id'] in self.proposals and self.proposals[p['id']]['proposal'] != p:
                raise ValueError('Proposal changed during retry')
            prepared.append(p)
        self.clock = now.isoformat()
        bars, coverage = bars or {}, coverage or {}
        for due in self.receivables:
            if not due['settled'] and due['due'] is not None and utc_time(due['due']) <= now:
                self.cash += due['cents']
                due['settled'] = True
                self._event('settlement', **due)
        refs = {}
        for contract in sorted(set(self.positions) | {p['contract'] for p in prepared}):
            refs[contract] = self._reference(contract, now, bars.get(contract, []))
        for contract, position in self.positions.items():
            ref, reason = refs[contract]
            terms = self.fixture['contracts'][contract]
            if now >= utc_time(terms['expiry_close']) - timedelta(minutes=15):
                self._issue('expiry_roll_physical_component_required', contract)
            position['mark'] = ref['price'] if ref else None
            if ref:
                position['last_mark_audit_only'] = ref['price']
                if ref['price'] <= .875 * position['entry_vwap']:
                    position['exit_intent'] = position['exit_intent'] or 'premium_stop'
            else:
                self.valuation_gaps.append(dict(at=self.clock, contract=contract, reason=reason,
                                               coverage_complete=coverage.get(contract) is True))
                if coverage.get(contract) is not True or reason in ('newest_bar_invalid', 'ambiguous_revision', 'revision_after_use'):
                    self.data_failure = True
            if contract in exits:
                position['exit_intent'] = position['exit_intent'] or 'strategy_exit'
        for contract in sorted(list(self.positions), key=lambda c: self._tie(self.proposals[self.positions[c]['proposal_id']]['proposal'])):
            position = self.positions[contract]
            ref, _ = refs[contract]
            if not position['exit_intent'] or ref is None:
                continue
            quantity = min(position['quantity'], self._capacity(ref))
            if quantity == 0:
                continue
            amount = self._fill('sell', contract, quantity, ref, position['proposal_id'])
            day = str(now.astimezone(NY).date())
            due = self.fixture['settlements'].get(day)
            self.receivables.append(dict(cents=amount, due=due, settled=False, contract=contract,
                                         proposal_id=position['proposal_id']))
            if due is None:
                self._issue('settlement_calendar_missing', contract)
            position['quantity'] -= quantity
            if position['quantity'] == 0:
                del self.positions[contract]
        for p in sorted(prepared, key=self._tie):
            record = self.proposals.setdefault(p['id'], dict(proposal=p, status='pending', attempts=[]))
            if record['status'] != 'pending':
                continue
            contract, signal = p['contract'], utc_time(p['signal_at'])
            terms = self.fixture['contracts'][contract]
            ref, reason = refs[contract]
            equity = self.equity()
            gate = expiry_entry_gate(terms['expiration_date'], now, target=p['target'],
                                    signal_qualifies=p['qualifies'], expiry_close=terms['expiry_close'],
                                    weekly_eligible=terms.get('weekly_eligible', False))
            if not signal + timedelta(seconds=1) <= now <= signal + timedelta(seconds=60):
                reason = 'outside_attempt_window'
            elif utc_time(terms['known_at']).astimezone(NY).date() >= signal.astimezone(NY).date():
                reason = 'prior_date_identity_missing'
            elif not gate['entry_eligible']:
                reason = gate['reason']
            elif self.unresolved or equity is None:
                reason = 'equity_or_liability_unresolved'
            elif len(self.positions) >= 5 or any(self.fixture['contracts'][c]['symbol'] == p['symbol'] for c in self.positions):
                reason = 'slot_or_underlying_occupied'
            elif ref is not None:
                budget = min(self.cash / 100, .1 * equity)
                unit = terms['multiplier'] * ref['price'] * 1.0015
                quantity = min(math.floor(budget / unit), self._capacity(ref))
                if quantity > 0:
                    amount = self._fill('buy', contract, quantity, ref, p['id'])
                    assert amount <= self.cash
                    self.cash -= amount
                    self.positions[contract] = dict(quantity=quantity, entry_vwap=ref['price'],
                        mark=ref['price'], last_mark_audit_only=ref['price'], exit_intent=None, proposal_id=p['id'])
                    record['status'] = 'filled'
                    reason = 'filled'
                else:
                    reason = 'size_ineligible'
            record['attempts'].append(dict(at=self.clock, reason=reason,
                coverage_complete=coverage.get(contract) is True))
            self._event('entry_attempt', proposal_id=p['id'], **record['attempts'][-1])
        self.last_equity = self.equity()
        self._check()

    def equity(self):
        if self.unresolved or any(p['mark'] is None for p in self.positions.values()):
            return None
        return self.cash / 100 + sum(r['cents'] / 100 for r in self.receivables if not r['settled']) + sum(
            p['quantity'] * self.fixture['contracts'][c]['multiplier'] * p['mark'] for c, p in self.positions.items())

    def finish_entry(self, proposal_id, *, window_coverage_complete):
        """Caller attests full attempt-window census; never inferred from one bar."""
        record = self.proposals[proposal_id]
        if self.clock is None or utc_time(self.clock) < utc_time(record['proposal']['signal_at']) + timedelta(seconds=60):
            raise ValueError('Entry window not finished')
        if record['status'] == 'pending':
            liquidity_reasons = {'reference_missing', 'reference_stale', 'size_ineligible',
                                 'slot_or_underlying_occupied', 'outside_attempt_window',
                                 'signal_not_qualified', 'outside_0_to_5_calendar_dte',
                                 'target_not_enabled', 'expiry_exit_cutoff_reached'}
            complete = window_coverage_complete is True and all(
                a['coverage_complete'] and a['reason'] in liquidity_reasons for a in record['attempts'])
            record['status'] = 'observed_unfilled' if complete else 'input_unresolved'
        return record['status']

    def outcome(self, *, at_boundary=False):
        """No win/return target is produced by this mechanics component."""
        if self.unresolved or self.data_failure or any(p['status'] == 'input_unresolved' for p in self.proposals.values()):
            status = 'input_unresolved'
        elif self.positions or any(not r['settled'] for r in self.receivables) or any(p['status'] == 'pending' for p in self.proposals.values()):
            status = 'right_censored_end' if at_boundary else 'open'
        else:
            status = 'settled'
        return dict(status=status, settled_cash_cents=self.cash,
                    receivable_cents=sum(r['cents'] for r in self.receivables if not r['settled']),
                    positions=deepcopy(self.positions), unresolved=deepcopy(self.unresolved),
                    valuation_gap_count=len(self.valuation_gaps), training_admitted=False)

    def _check(self):
        buys = sum(e['cash_cents'] for e in self.events if e['kind'] == 'fill' and e['side'] == 'buy')
        settled = sum(r['cents'] for r in self.receivables if r['settled'])
        assert self.cash == 10_000_000 - buys + settled and self.cash >= 0
        assert all(isinstance(p['quantity'], int) and p['quantity'] > 0 for p in self.positions.values())
        assert len({self.fixture['contracts'][c]['symbol'] for c in self.positions}) == len(self.positions) <= 5
        quantities, used, sales = {}, {}, 0
        for event in self.events:
            if event['kind'] != 'fill':
                continue
            contract, key, q = event['contract'], event['reference']['key'], event['quantity']
            quantities[contract] = quantities.get(contract, 0) + (q if event['side'] == 'buy' else -q)
            used[key] = used.get(key, 0) + q
            assert quantities[contract] >= 0 and used[key] <= math.floor(.01 * event['reference']['volume'])
            if event['side'] == 'sell':
                sales += event['cash_cents']
        assert used == self.used and sales == sum(r['cents'] for r in self.receivables)
        assert {c: q for c, q in quantities.items() if q} == {c: p['quantity'] for c, p in self.positions.items()}

    def snapshot(self):
        return dict(schema=SCHEMA, state=json.loads(canonical(self.__dict__)))

    @classmethod
    def restore(cls, snapshot):
        if snapshot['schema'] != SCHEMA or snapshot['state']['source'] != source_hash():
            raise ValueError('Snapshot schema/source mismatch')
        obj = cls(snapshot['state']['fixture'])
        obj.__dict__.update(deepcopy(snapshot['state']))
        obj._check()
        return obj
