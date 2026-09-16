"""Funded physical expiry ledger. Evidence acquisition remains a separate gate.

No intrinsic-value sale, borrowed stock, or external exercise capital is created.
Fractional quantities are an explicit pro-rata *research* convention.
"""
from dataclasses import dataclass, asdict
from decimal import Decimal
import math
import pandas as pd

from nn_meta.v7.execution import CashLedger, QuoteUnavailable
from options.data.provider import parse_occ_symbol


@dataclass(frozen=True)
class PhysicalPolicy:
    exercise_threshold: float = .01
    exercise_fee_per_contract: float = 0.
    stock_fee_fraction: float = .001
    stock_slippage_fraction: float = .0005
    fractional_policy: str = 'pro-rata-paper'

    def __post_init__(self):
        costs = (self.exercise_threshold, self.exercise_fee_per_contract,
                 self.stock_fee_fraction, self.stock_slippage_fraction)
        if (any(isinstance(v, bool) or not math.isfinite(v) or v < 0 for v in costs)
                or self.exercise_threshold <= 0
                or self.stock_fee_fraction + self.stock_slippage_fraction >= 1
                or self.fractional_policy not in ('pro-rata-paper', 'whole-contracts')):
            raise ValueError('Invalid explicit physical exercise policy')


class SettlementCalendar:
    """Captured settlement dates, distinct from an equity trading calendar.

    Settlement is conservatively available at the next trading open *after*
    the settlement date. This avoids assuming intraday broker release times.
    """
    def __init__(self, document, trading_calendar):
        self.document, self.trading = document, trading_calendar
        days = document['business_dates']
        if (document.get('schema') != 'v7-settlement-calendar-v1'
                or not document.get('source_identity') or not days
                or days != sorted(set(days))
                or any(not document['coverage_start'] <= d <= document['coverage_end'] for d in days)):
            raise ValueError('Dated settlement calendar with source identity required')
        for day in days:
            if pd.Timestamp(day).date().isoformat() != day:
                raise ValueError('ISO settlement dates required')
        self.days = days

    def settlement(self, event_ns):
        if type(event_ns) is not int or event_ns < 0:
            raise ValueError('Exact nonnegative settlement event nanoseconds required')
        day = pd.Timestamp(event_ns, unit='ns', tz='UTC').tz_convert('America/New_York').date().isoformat()
        if not self.document['coverage_start'] <= day <= self.document['coverage_end']:
            raise ValueError('Event lies outside captured settlement coverage')
        # Stocks can trade on banking holidays. The trade/exercise event is T,
        # even when that date is not itself a settlement business day. Count
        # T+1/T+2 only from later captured settlement dates, never roll T first.
        if day not in self.days and self.trading.bounds(day) is None:
            raise ValueError('Event lacks a captured trading or settlement date')
        delay = 2 if day < '2024-05-28' else 1
        later = [d for d in self.days if d > day]
        if len(later) < delay:
            raise ValueError('Settlement calendar does not cover label horizon')
        settled_on = later[delay-1]
        following = next((d for d in sorted(self.trading.sessions) if d > settled_on), None)
        if following is None:
            raise ValueError('Trading calendar does not cover settlement availability')
        return settled_on, int(self.trading.bounds(following)[0].tz_localize('UTC').value)


class PhysicalLedger(CashLedger):
    def __init__(self, *args, settlement_calendar, physical_policy=PhysicalPolicy(), **kwargs):
        super().__init__(*args, **kwargs)
        self.settlement_calendar = settlement_calendar
        self.physical_policy = physical_policy
        self.commitments = {}
        self.entry_reservations = {}
        self.shares = {}  # Settled stock only, acquired with this ledger's cash.
        self.completed = {}

    @property
    def available_cash(self):
        return self.cash - sum(self.entry_reservations.values()) - sum(
            max(0., -v['cash_delta']) for v in self.commitments.values())

    def reserve_entry(self, key, amount):
        if key in self.entry_reservations or not math.isfinite(amount) or not 0 < amount <= self.available_cash:
            return False
        self.entry_reservations[key] = amount
        return True

    def buy(self, key, symbol, fill, *, equity, decision_date, budget=None, roll_of=None, security_id=None):
        if not security_id:
            raise ValueError('Physical positions require an explicit security identity')
        own = self.entry_reservations.get(key, 0.)
        available = self.available_cash + own
        budget = min(available, self.fraction * equity if budget is None else budget)
        if self.physical_policy.fractional_policy == 'whole-contracts' and budget > 0:
            self._validate_fill(fill)
            unit = fill['price'] * self.policy.multiplier * (1+self.policy.fee+self.policy.slippage)
            budget = math.floor(budget / unit) * unit
        accepted = super().buy(key, symbol, fill, equity=equity, decision_date=decision_date,
                               budget=budget, roll_of=roll_of)
        if accepted:
            self.entry_reservations.pop(key, None)
            self.positions[key]['phase'] = 'option'
            self.positions[key]['security_id'] = security_id
        return accepted

    def sell(self, key, fill):
        if self.positions[key].get('phase') != 'option':
            raise ValueError('Physical-delivery position cannot sell an expired option')
        return super().sell(key, fill)

    def _event(self, key, clock, kind, cash_delta=0., **fields):
        self._clock(clock)
        self.events.append(dict(key=key, sip_timestamp=clock, kind=kind,
                                cash_delta=cash_delta, **fields))

    def expire(self, key, clock, *, metadata, reference):
        """Reference must be a receipt-backed official price/instruction record.

        Its available_ns is a data observation time, not the download time.
        Unknown deliverables and late references are errors, not zero outcomes.
        """
        if metadata.get('settlement_mode') == 'cash_merger':
            return self._cash_merger_expiry(key, clock, metadata=metadata, reference=reference)
        p = self.positions[key]
        if p.get('phase') != 'option':
            raise ValueError('Expiry may be processed only once')
        root, expiry, right, strike = parse_occ_symbol(p['contract'])
        day = pd.Timestamp(clock, unit='ns', tz='UTC').tz_convert('America/New_York').date().isoformat()
        if (metadata.get('contract') != p['contract'] or metadata.get('date') != expiry.isoformat()
                or metadata.get('expiry') != expiry or metadata.get('underlying') != root
                or metadata.get('right') != right or metadata.get('strike') != strike
                or metadata.get('multiplier') != 100 or not metadata.get('metadata_receipt_sha256')
                or reference.get('contract') != p['contract'] or reference.get('date') != expiry.isoformat()
                or reference.get('security_id') != p['security_id']
                or not reference.get('source_identity') or reference.get('instruction') != 'exercise-by-exception'
                or type(reference.get('available_ns')) is not int
                or reference['available_ns'] > clock or type(reference.get('exercise_ns')) is not int
                or clock != reference['exercise_ns'] or day != expiry.isoformat()
                or type(reference.get('reference_ns')) is not int
                or not 0 <= reference['reference_ns'] <= reference['available_ns']
                or not self._reference_date_admitted(reference, expiry)):
            raise ValueError('Exact dated deliverable, official reference and exercise clock evidence required')
        price = reference.get('price')
        if isinstance(price, bool) or not isinstance(price, (float, int)) or not math.isfinite(price) or price <= 0:
            raise ValueError('Positive official expiration reference required')
        itm = (Decimal(str(price))-Decimal(str(strike))) * (1 if right == 'C' else -1)
        if itm < Decimal(str(self.physical_policy.exercise_threshold)):
            self._event(key, clock, 'expiration_nonexercise', reference_identity=reference['source_identity'],
                        contract=p['contract'], realized_pnl=-p['cost'])
            del self.positions[key]
            self.completed[key] = clock
            return 'expired_unexercised'
        shares = p['quantity'] * 100
        fees = p['quantity'] * self.physical_policy.exercise_fee_per_contract
        if self.physical_policy.fractional_policy == 'whole-contracts' and not math.isclose(p['quantity'], round(p['quantity']), abs_tol=1e-9):
            raise ValueError('Fractional physical quantity was not admitted')
        cash_delta = (-shares * strike if right == 'C' else shares * strike) - fees
        # Put proceeds do not fund their own fee until settlement.
        if (right == 'C' and -cash_delta > self.available_cash + 1e-8) or (right == 'P' and fees > self.available_cash + 1e-8):
            return 'unresolved_exercise_funding'
        held = self.shares.get((p['symbol'], p['security_id']), 0.)
        if right == 'P' and held + 1e-8 < shares:
            return 'unresolved_share_delivery'
        settled_on, available = self.settlement_calendar.settlement(clock)
        self._event(key, clock, 'exercise', contract=p['contract'], shares=shares,
                    reference_identity=reference['source_identity'],
                    metadata_receipt_sha256=metadata['metadata_receipt_sha256'], policy=asdict(self.physical_policy))
        # Put delivery removes reserved shares from free inventory immediately.
        if right == 'P':
            self.shares[(p['symbol'], p['security_id'])] = held - shares
            if fees:
                self.cash -= fees
                self._event(key, clock, 'exercise_fee', cash_delta=-fees)
                cash_delta += fees
        self.commitments[key] = dict(cash_delta=cash_delta, settled_on=settled_on,
                                    available_ns=available, right=right, shares=shares)
        p.update(phase='delivery_pending', deliverable_shares=shares, right=right)
        self._event(key, clock, 'delivery_commitment', payable=max(-cash_delta, 0.),
                    receivable=max(cash_delta, 0.), settled_on=settled_on, available_ns=available)
        return 'exercise_committed'

    @staticmethod
    def _reference_date_admitted(reference, expiry):
        """A prior-day price requires an exact, separately bound OCC exception."""
        observed = pd.Timestamp(reference['reference_ns'], unit='ns', tz='UTC').tz_convert('America/New_York').date()
        if observed == expiry:
            return True
        override = reference.get('official_override', {})
        return (observed < expiry and override.get('authority') == 'OCC'
                and bool(override.get('notice_identity'))
                and type(override.get('available_ns')) is int
                and reference['reference_ns'] <= override['available_ns'] <= reference['available_ns']
                and all(override.get(k) == reference.get(k) for k in
                        ('contract', 'security_id', 'date', 'reference_ns', 'price')))

    def _cash_merger_expiry(self, key, clock, *, metadata, reference):
        """Mandatory OCC cash deliverable, never an assumed option market sale."""
        p = self.positions[key]
        root, expiry, right, strike = parse_occ_symbol(p['contract'])
        day = pd.Timestamp(clock, unit='ns', tz='UTC').tz_convert('America/New_York').date().isoformat()
        cash = metadata.get('cash_deliverable_per_contract')
        if (p.get('phase') != 'option' or metadata.get('contract') != p['contract']
                or metadata.get('expiry') != expiry or metadata.get('underlying') != root
                or metadata.get('right') != right or metadata.get('strike') != strike
                or metadata.get('multiplier') != 100 or not metadata.get('metadata_receipt_sha256')
                or metadata.get('security_id') != p['security_id']
                or metadata.get('date') != day or day > expiry.isoformat()
                or type(metadata.get('effective_ns')) is not int
                or type(metadata.get('available_ns')) is not int
                or not 0 <= metadata['available_ns'] <= clock
                or not 0 <= metadata['effective_ns'] <= clock
                or isinstance(cash, bool) or not isinstance(cash, (int, float))
                or not math.isfinite(cash) or cash <= 0
                or reference.get('instruction') != 'cash-exercise-by-exception'
                or not reference.get('source_identity')
                or reference.get('exercise_ns') != clock
                or type(reference.get('available_ns')) is not int
                or not max(metadata['effective_ns'], metadata['available_ns']) <= reference['available_ns'] <= clock
                or any(reference.get(k) != metadata.get(k) for k in
                       ('contract', 'security_id', 'date', 'cash_deliverable_per_contract'))):
            raise ValueError('Exact dated OCC cash deliverable and exercise evidence required')
        difference = (Decimal(str(cash)) - Decimal(str(strike))*100) * (1 if right == 'C' else -1)
        if difference < Decimal(str(self.physical_policy.exercise_threshold))*100:
            self._event(key, clock, 'cash_expiration_nonexercise', contract=p['contract'],
                        reference_identity=reference['source_identity'], realized_pnl=-p['cost'])
            del self.positions[key]
            self.completed[key] = clock
            return 'expired_unexercised'
        fees = p['quantity'] * self.physical_policy.exercise_fee_per_contract
        if fees > self.available_cash + 1e-8:
            return 'unresolved_exercise_funding'
        settled_on, available = self.settlement_calendar.settlement(clock)
        receivable = p['quantity'] * float(difference)
        self._event(key, clock, 'cash_merger_exercise', cash_delta=-fees, contract=p['contract'],
                    receivable=receivable, cash_deliverable_per_contract=cash,
                    reference_identity=reference['source_identity'],
                    metadata_receipt_sha256=metadata['metadata_receipt_sha256'])
        self.cash -= fees
        self.commitments[key] = dict(cash_delta=receivable, settled_on=settled_on,
                                    available_ns=available, right='cash', shares=0.)
        p['phase'] = 'cash_merger_pending'
        return 'cash_exercise_committed'

    def acquire_inventory(self, key, symbol, security_id, quantity, fill):
        """Buy put-delivery inventory from existing cash, with settled delivery.

        This optional funded path is not called automatically by the strategy.
        No initial shares can be injected without a corresponding cash event.
        """
        if (not security_id or key in self.positions or len(self.positions) >= self.slots
                or any(p['symbol'] == symbol for p in self.positions.values())
                or not math.isfinite(quantity) or quantity <= 0):
            raise ValueError('Distinct funded inventory position required')
        self._stock_fill(fill, symbol, security_id, quantity, side='buy')
        cost = quantity * fill['price'] * (1+self.physical_policy.stock_fee_fraction+self.physical_policy.stock_slippage_fraction)
        if cost > self.available_cash:
            return False
        settled_on, available = self.settlement_calendar.settlement(fill['sip_timestamp'])
        self._event(key, fill['sip_timestamp'], 'inventory_purchase', payable=cost, shares=quantity,
                    price=fill['price'], capture_identity=fill['capture_identity'])
        self.positions[key] = dict(symbol=symbol, security_id=security_id, phase='inventory_purchase_pending',
                                   deliverable_shares=quantity, right='C')
        self.commitments[key] = dict(cash_delta=-cost, settled_on=settled_on,
                                    available_ns=available, right='C', shares=quantity)
        return True

    def settle(self, clock):
        self._clock(clock)
        for key, c in list(self.commitments.items()):
            if c['available_ns'] > clock:
                continue
            p = self.positions[key]
            self.cash += c['cash_delta']
            self._event(key, clock, 'settlement', cash_delta=c['cash_delta'], settled_on=c['settled_on'])
            del self.commitments[key]
            if p['phase'] == 'inventory_purchase_pending':
                stock_key = p['symbol'], p['security_id']
                self.shares[stock_key] = self.shares.get(stock_key, 0.) + c['shares']
                self._event(key, clock, 'inventory_delivery', shares=c['shares'])
                del self.positions[key]
            elif p['phase'] in ('stock_sale_pending', 'cash_merger_pending') or c['right'] == 'P':
                del self.positions[key]
                self.completed[key] = clock
            else:
                p['phase'] = 'stock'
                self._event(key, clock, 'stock_delivery', shares=c['shares'])

    def _stock_fill(self, fill, symbol, security_id, quantity, *, side):
        self._validate_fill(fill)
        if (fill.get('symbol') != symbol or fill.get('security_id') != security_id or fill.get('side') != side
                or fill.get('provider') != 'alpaca' or not fill.get('capture_identity')
                or not math.isfinite(fill.get('reported_size', float('nan')))
                or fill['reported_size'] < quantity
                or type(fill.get('decision_ns')) is not int
                or fill['sip_timestamp'] < max(self.last_clock, fill['decision_ns'] + self.policy.latency_ns)
                or fill['sip_timestamp'] > fill['decision_ns'] + self.policy.entry_deadline_ns):
            raise ValueError('Eligible sized observed Alpaca stock bid required')
        day = pd.Timestamp(fill['sip_timestamp'], unit='ns', tz='UTC').tz_convert('America/New_York').date().isoformat()
        bounds = self.settlement_calendar.trading.bounds(day)
        if bounds is None or not bounds[0].tz_localize('UTC').value <= fill['sip_timestamp'] < bounds[1].tz_localize('UTC').value:
            raise ValueError('Stock quote must lie inside its captured regular session')

    def liquidate_stock(self, key, fill):
        p = self.positions[key]
        if p['phase'] != 'stock':
            raise ValueError('Settled stock delivery required before liquidation')
        if fill is None:
            return None
        self._stock_fill(fill, p['symbol'], p['security_id'], p['deliverable_shares'], side='sell')
        settled_on, available = self.settlement_calendar.settlement(fill['sip_timestamp'])
        net = p['deliverable_shares'] * fill['price'] * (1-self.physical_policy.stock_fee_fraction-self.physical_policy.stock_slippage_fraction)
        self._event(key, fill['sip_timestamp'], 'stock_sale', shares=p['deliverable_shares'],
                    price=fill['price'], capture_identity=fill['capture_identity'], receivable=net)
        self.commitments[key] = dict(cash_delta=net, settled_on=settled_on,
                                    available_ns=available, right='C', shares=0.)
        p['phase'] = 'stock_sale_pending'
        return net

    def equity(self, clock_ns, tapes, stock_archive=None):
        if clock_ns < self.last_clock:
            raise ValueError('Equity cannot precede recorded events')
        value = self.cash
        def stock_bid(symbol, security_id):
            if stock_archive is None:
                raise QuoteUnavailable('Physical stock mark capture required')
            mark = stock_archive.mark(symbol, clock_ns)
            if (mark.get('security_id') != security_id or not mark.get('capture_identity')
                    or type(mark.get('sip_timestamp')) is not int
                    or not 0 <= clock_ns-mark['sip_timestamp'] <= self.policy.max_mark_age_ns
                    or not math.isfinite(mark.get('bid', float('nan'))) or mark['bid'] <= 0):
                raise QuoteUnavailable('Fresh security-bound stock mark required')
            return mark['bid']
        for key, p in self.positions.items():
            phase = p.get('phase')
            if phase == 'option':
                value += p['quantity'] * 100 * tapes[p['contract']].mark(clock_ns)['bid']
            elif phase in ('stock', 'delivery_pending', 'inventory_purchase_pending') and p['right'] == 'C':
                value += p['deliverable_shares'] * stock_bid(p['symbol'], p['security_id'])
            if key in self.commitments:
                value += self.commitments[key]['cash_delta']
        for (symbol, security_id), quantity in self.shares.items():
            if quantity:
                value += quantity * stock_bid(symbol, security_id)
        return value

    def reconcile(self):
        result = super().reconcile()
        if self.available_cash < -1e-7 or any(v < -1e-9 for v in self.shares.values()):
            raise ValueError('Physical commitments exceed funded resources')
        return {**result, 'available_cash': self.available_cash, 'pending_settlements': len(self.commitments)}
