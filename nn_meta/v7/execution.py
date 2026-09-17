"""Observed-quote V7 execution and shared cash ledger; missing exits stay open."""
from __future__ import annotations
from dataclasses import asdict,dataclass
import math
import numpy as np
from options.data.provider import parse_occ_symbol
from options.paper_pricing import MIDPOINT_POLICY, option_midpoint


@dataclass(frozen=True)
class QuotePolicy:
    latency_ns:int=1_000_000_000
    entry_deadline_ns:int=60_000_000_000
    max_mark_age_ns:int=30_000_000_000
    fee:float=.001
    slippage:float=.0005
    multiplier:int=100
    min_reported_size:float=1
    option_price_basis:str=MIDPOINT_POLICY

    def __post_init__(self):
        if (any(type(v) is not int or v<0 for v in
                (self.latency_ns,self.entry_deadline_ns,self.max_mark_age_ns))
                or self.latency_ns>self.entry_deadline_ns or self.multiplier!=100
                or not all(math.isfinite(v) and v>=0 for v in (self.fee,self.slippage,self.min_reported_size))
                or self.fee+self.slippage>=1 or self.min_reported_size<=0
                or self.option_price_basis!=MIDPOINT_POLICY):
            raise ValueError('Invalid quote policy')


class QuoteUnavailable(ValueError):pass


class CaptureUnavailable(QuoteUnavailable):
    """The required provider capture is incomplete, distinct from a sparse market."""


def fill_clock(fill):
    """Simulation execution clock; retain the original quote timestamp separately."""
    return fill.get('execution_ns', fill['sip_timestamp'])


class QuoteTape:
    def __init__(self,records,manifest,*,contract,policy=QuotePolicy()):
        from options.data.massive_ticks import verify_capture
        verify_capture(records,manifest,contract=contract,kind='quotes',
                       start_ns=manifest['start_ns'],end_ns=manifest['end_ns'])
        from copy import deepcopy
        self.records=deepcopy(records);self.manifest=deepcopy(manifest);self.contract=contract.removeprefix('O:')
        self.stamps=np.array([r['sip_timestamp'] for r in records],dtype=np.int64)
        if np.any(self.stamps[1:] < self.stamps[:-1]):
            raise ValueError('Quote timeline must be ordered')
        self.policy=policy

    def valid(self,row):
        vals=[row.get(k) for k in ('bid_price','ask_price','bid_size','ask_size')]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in vals):return False
        bid,ask,bs,az=vals
        if not (0<bid<=ask and bs>=self.policy.min_reported_size and az>=self.policy.min_reported_size):return False
        try:option_midpoint(row)
        except ValueError:return False
        return True

    def first_fill(self,decision_ns,*,side,deadline_ns=None):
        if side not in ('buy','sell'):raise ValueError('Explicit buy/sell required')
        start=decision_ns+self.policy.latency_ns
        end=decision_ns+self.policy.entry_deadline_ns if deadline_ns is None else deadline_ns
        if type(decision_ns) is not int or decision_ns < 0 or type(end) is not int or end < start:
            raise ValueError('Invalid fill window chronology')
        if self.manifest['start_ns']>start or self.manifest['end_ns']<=end:
            raise CaptureUnavailable('Fill window is not completely captured')
        for i in range(int(self.stamps.searchsorted(start)),int(self.stamps.searchsorted(end,side='right'))):
            row=self.records[i]
            if self.valid(row):
                return {'contract':self.contract,'side':side,'decision_ns':decision_ns,
                        'sip_timestamp':int(self.stamps[i]),**option_midpoint(row),
                        'reported_size':row['ask_size'] if side=='buy' else row['bid_size']}
        return None  # Complete observations, but no eligible quote in the window.

    def mark(self,clock_ns):
        if not self.manifest['start_ns']<=clock_ns<self.manifest['end_ns']:
            raise QuoteUnavailable('Mark clock is outside complete capture')
        i=int(self.stamps.searchsorted(clock_ns,side='right'))-1
        if i<0 or clock_ns-int(self.stamps[i])>self.policy.max_mark_age_ns:
            raise QuoteUnavailable('No fresh causal mark')
        row=self.records[i]
        # A newer invalid quote invalidates the book; never search back to an
        # older positive quote through a crossed/zero-sided market update.
        if not self.valid(row):raise QuoteUnavailable('Latest market is invalid')
        return {**option_midpoint(row),'sip_timestamp':int(self.stamps[i])}


class CashLedger:
    def __init__(self,capital=100_000.,*,slots=5,fraction=.1,policy=QuotePolicy()):
        if not math.isfinite(capital) or capital<=0 or slots<1 or not 0<fraction<=1:
            raise ValueError('Invalid portfolio policy')
        self.initial=self.cash=float(capital);self.slots=slots;self.fraction=fraction
        self.policy=policy;self.positions={};self.events=[];self.last_clock=-1

    def _clock(self,clock):
        if type(clock) is not int or clock<self.last_clock:raise ValueError('Ledger events must be chronological')
        self.last_clock=clock

    def equity(self,clock_ns,tapes):
        if type(clock_ns) is not int or clock_ns < self.last_clock:
            raise ValueError('Equity cannot precede a recorded fill')
        return self.cash+sum(p['quantity']*self.policy.multiplier*tapes[p['contract']].mark(clock_ns)['price']
                             for p in self.positions.values())

    def _validate_fill(self,fill):
        if (not isinstance(fill,dict) or isinstance(fill.get('price'),bool)
                or not isinstance(fill.get('price'),(int,float))
                or not math.isfinite(fill['price']) or fill['price']<=0
                or type(fill.get('sip_timestamp')) is not int or fill['sip_timestamp']<0):
            raise ValueError('Positive finite timestamped fill required')
        if ('execution_ns' in fill and (type(fill['execution_ns']) is not int
                or not 0 <= fill['execution_ns']-fill['sip_timestamp'] <= self.policy.max_mark_age_ns
                or fill.get('decision_ns',fill['execution_ns']) > fill['execution_ns'])):
            raise ValueError('Simulated execution requires a fresh causal quote and decision')

    def buy(self,key,symbol,fill,*,equity,decision_date,budget=None,roll_of=None):
        self._validate_fill(fill)
        root,expiry,_,_=parse_occ_symbol(fill['contract'])
        import pandas as pd
        fill_date=pd.Timestamp(fill_clock(fill),unit='ns',tz='UTC').tz_convert('America/New_York').date()
        if fill_date < decision_date:
            raise ValueError('Fill cannot precede its decision date')
        dte=(expiry-fill_date).days
        if not 1<=dte<=9:raise ValueError('Every entry/roll purchase requires actual 1–9 DTE')
        if fill['side']!='buy' or root!=symbol.replace('.', ''):raise ValueError('Fill security identity mismatch')
        if key in self.positions or len(self.positions)>=self.slots:return False
        if any(p['symbol']==symbol for p in self.positions.values()):return False
        if not math.isfinite(equity) or equity<=0:raise ValueError('Positive observed portfolio equity required')
        budget=min(self.cash,self.fraction*equity) if budget is None else min(self.cash,budget)
        if not math.isfinite(budget) or budget<=0:return False
        gross_price=fill['price']*self.policy.multiplier
        quantity=budget/(gross_price*(1+self.policy.fee+self.policy.slippage))
        # Fractional paper allocation matches the existing research baseline.
        # Reported size is recorded, not represented as a guaranteed fill.
        self._clock(fill_clock(fill))
        self.cash-=budget
        self.positions[key]={'symbol':symbol,'contract':fill['contract'],'quantity':quantity,'cost':budget,
                             'entry_midpoint':fill['price']}
        self.events.append({**fill,'key':key,'quantity':quantity,'cash_delta':-budget,'roll_of':roll_of,
                            'actual_dte':dte,'policy':asdict(self.policy),'fractional_paper':True})
        return True

    def sell(self,key,fill):
        position=self.positions[key]
        if fill is None:return None
        self._validate_fill(fill)
        if fill['side']!='sell' or fill['contract']!=position['contract']:raise ValueError('Exit identity mismatch')
        self._clock(fill_clock(fill))
        proceeds=position['quantity']*self.policy.multiplier*fill['price']*(1-self.policy.fee-self.policy.slippage)
        self.cash+=proceeds;del self.positions[key]
        self.events.append({**fill,'key':key,'quantity':position['quantity'],'cash_delta':proceeds,
                            'realized_pnl':proceeds-position['cost']})
        return proceeds

    def reconcile(self):
        expected=self.initial+sum(e['cash_delta'] for e in self.events)
        if not math.isclose(expected,self.cash,abs_tol=1e-7,rel_tol=1e-12):raise ValueError('Cash ledger does not reconcile')
        return {'cash':self.cash,'open_positions':len(self.positions),'events':len(self.events)}
