"""ETFE isolated-path label kernel v1: decision-clock rows, earliest firing-variant exit.

Implements the execution contract (ETFE_EXECUTION_20261003) for one isolated $100,000 account per
row, under the row-unit amendment (ETFE_ROW_UNIT_AMENDMENT_20261007), dated-input policy v1 and
the envelope capture. It jumps between event clocks instead of stepping every second; the
synthetic `integration_ledger.Scheduler` is the per-second reference it is parity-tested against.

Reference rules mirrored exactly:
- bar availability start+61 s (+stress lag), fresh until end+60 s; the newest known bar is the
  only candidate (no backward search); VWAP/volume/count must be positive;
- clock order settle -> marks/stop -> exits -> entries; capacity floor(1% volume) minus volume
  this path already used on that bar; one cents rounding (half-even) per fill;
- entry attempts in [t+1 s, t+60 s] before the expiry cutoff on 0-5 DTE contracts;
- stop at VWAP <= 0.875 x the leg's entry VWAP; exits latch until sold or expired; no trade at or
  after the option close; unsold legs face OCC $0.01 exercise at the closing-auction reference;
- calls need full strike cash and liquidate at fresh SIP bids from settlement; puts need owned
  shares (never in an isolated account) -> funding_unresolved;
- any required observation or settlement past the fixed end -> right_censored_end.
"""
import bisect
from dataclasses import dataclass,field
from datetime import date,datetime,timedelta
from decimal import Decimal,ROUND_HALF_EVEN
import math

import numpy as np

NS=1_000_000_000
MINUTE=60*NS
CASH0=10_000_000  # cents
MULT=100
END_NS=int(datetime.fromisoformat('2026-10-03T04:00:00+00:00').timestamp())*NS
LIQUIDITY={'outside_0_to_5_calendar_dte','target_not_enabled','expiry_exit_cutoff_reached'}
# fill_rule: 'next_bar_vwap' (amendment 2026-10-07, default) or 'signal_bar_vwap' (reference-ledger parity).
BASELINE=dict(lag_seconds=1,participation=.01,cost_multiplier=1,min_volume=1,min_count=1,exercise_fee=0.0,quote_lag_seconds=1,
    fill_rule='next_bar_vwap',stop_fraction=.875)


def latest(credits,*extra):
    """Latest dated settlement among credits and extra clocks; None dues are handled by run()."""
    return max([d for _,d in credits if d is not None]+list(extra))


def cents(value):
    return int(Decimal(str(value)).quantize(Decimal('.01'),rounding=ROUND_HALF_EVEN)*100)


@dataclass
class Bars:
    """One contract's captured 1-minute bars (start ns ascending) and captured coverage [lo, hi)."""
    start:np.ndarray
    vwap:np.ndarray
    volume:np.ndarray
    count:np.ndarray
    lo:int
    hi:int


@dataclass
class Quotes:
    """One underlying's captured SIP quotes (t ns ascending) and captured windows [(lo, hi)]."""
    t:np.ndarray
    bid:np.ndarray
    ask:np.ndarray
    bid_size:np.ndarray
    ask_size:np.ndarray
    windows:list
    available:np.ndarray=None  # captured availability; default t + lag


@dataclass
class Market:
    """Everything the kernel reads; built by `label_inputs` from frozen artifacts."""
    bars:dict                 # symbol -> Bars
    quotes:dict               # ticker -> Quotes
    contracts:dict            # symbol -> (ticker, right 'call'/'put', expiry date, strike, available_from date)
    by_expiry:dict            # (ticker, right, expiry) -> sorted [(strike, symbol)]
    sessions:dict             # date -> (open_ns, close_ns)
    equity_settle:dict        # trade date -> settlement date (provider calendar)
    settle_days:list          # sorted bank/market settlement dates
    references:dict           # (ticker, expiry date) -> official close price or None
    weekly:set                # tickers with weekly targets 2/4
    expiry_overrides:dict=field(default_factory=dict)  # listed expiry -> dated effective expiry session


@dataclass
class Path:
    status:str='open'
    reason:str=''
    debit:int=0               # A: initial option cash debit (cents)
    pnl:int=0                 # P: net cash P&L across all legs (cents)
    quantity:int=0
    entry_vwap:float=0.0
    exit_kind:str=''
    terminal_ns:int=0
    rolls:int=0
    pin:bool=False
    spent:int=0
    prior:list=field(default_factory=list)
    events:list=field(default_factory=list)


class Kernel:
    def __init__(self,market,policy=None):
        self.m=market;self.p=dict(BASELINE,**(policy or {}))
        self.lag=int(self.p['lag_seconds']*NS);self.cm=self.p['cost_multiplier'];self.cost=.0015*self.cm  # sizing unit, as reference
        self.end=int(self.p.get('end_ns',END_NS));self.qlag=int(self.p['quote_lag_seconds']*NS)  # publication-lag stress applies to bars only
        if self.p['fill_rule'] not in ('next_bar_vwap','signal_bar_vwap'):raise ValueError('Unknown fill rule')
        self.next_bar=self.p['fill_rule']=='next_bar_vwap'

    # ---- references -------------------------------------------------------------------------
    def ref(self,bars,now):
        """Index of the newest bar known at `now` if fresh and valid, else None (no backward search)."""
        i=bisect.bisect_right(bars.start,now-MINUTE-self.lag)-1
        if i<0 or now>bars.start[i]+2*MINUTE:return None
        if not (bars.vwap[i]>0 and bars.volume[i]>=self.p['min_volume'] and bars.count[i]>=self.p['min_count']):return None
        return i

    def covered(self,bars,now):
        return bars is not None and bars.lo<=now<bars.hi

    def quote(self,ticker,now,regular_start=False):
        """Newest SIP quote known at `now` (t + lag <= now), age <= 30 s, positive, noncrossed.

        `now - lag` must fall inside a captured window [lo, hi). If no captured quote lies in
        [lo, now - lag], an uncaptured fresh quote could precede lo unless now - 30 s >= lo or the
        window starts at the regular open (`regular_start`; pre-open quotes are not eligible).
        """
        q=self.m.quotes.get(ticker)
        if q is None:return None,'quote_uncaptured'
        known=now-self.qlag;win=[lo for lo,hi in q.windows if lo<=known<hi]
        if not win:return None,'quote_uncaptured'
        lo=win[0]
        i=bisect.bisect_right(q.t,known)-1 if q.available is None else bisect.bisect_right(q.available,now)-1
        if i<0 or q.t[i]<lo:
            return (None,'quote_stale') if now-30*NS>=lo or regular_start else (None,'quote_uncaptured')
        if now-q.t[i]>30*NS:return None,'quote_stale'
        if not (q.bid[i]>0 and q.ask[i]>0 and q.bid_size[i]>0 and q.ask_size[i]>0 and q.bid[i]<=q.ask[i]):return None,'quote_invalid'
        return i,None

    # ---- calendar ---------------------------------------------------------------------------
    @staticmethod
    def ny_date(ns):
        from zoneinfo import ZoneInfo
        return datetime.fromtimestamp(ns/NS,ZoneInfo('America/New_York')).date()

    def option_due(self,trade_date):
        i=bisect.bisect_right(self.m.settle_days,trade_date)
        return self.at_open(self.m.settle_days[i]) if i<len(self.m.settle_days) else None

    def equity_due(self,trade_date):
        d=self.m.equity_settle.get(trade_date)
        return None if d is None else self.at_open(d)

    def at_open(self,day):
        """Settled funds/delivery available 09:30 New York on the dated settlement day."""
        from zoneinfo import ZoneInfo
        return int(datetime(day.year,day.month,day.day,9,30,tzinfo=ZoneInfo('America/New_York')).timestamp())*NS

    def effective(self,expiry):
        return self.m.expiry_overrides.get(expiry,expiry)

    def expiry_close(self,expiry):
        s=self.m.sessions.get(self.effective(expiry))
        return None if s is None else s[1]

    # ---- gates ------------------------------------------------------------------------------
    def gate(self,symbol,attempt_ns,target):
        ticker,_,expiry,_,avail=self.m.contracts[symbol]
        targets=(0,1,5)+((2,4) if ticker in self.m.weekly else ())
        if target not in targets:return 'target_not_enabled'
        day=self.ny_date(attempt_ns);dte=(expiry-day).days
        if not 0<=dte<=5:return 'outside_0_to_5_calendar_dte'
        if avail is None or avail>day:return 'prior_date_identity_missing'
        close=self.expiry_close(expiry)
        if close is None and expiry<=max(self.m.sessions):return 'expiry_close_unresolved'
        if close is not None and attempt_ns>=close-15*MINUTE:return 'expiry_exit_cutoff_reached'
        return None

    # ---- fills ------------------------------------------------------------------------------
    def fill(self,path,side,qty,price):
        # Reference order of float operations: fee and slippage separately, then one half-even rounding.
        gross=float(qty*MULT*price);fee,slip=gross*.001*self.cm,gross*.0005*self.cm
        amount=cents(gross+fee+slip if side=='buy' else gross-fee-slip)
        if side=='buy':path.spent+=amount
        return amount

    def valid_bar(self,bars,i):
        return bars.vwap[i]>0 and bars.volume[i]>=self.p['min_volume'] and bars.count[i]>=self.p['min_count']

    def sell(self,path,bars,used,qty,start_ns,stop_ns,due_by_day):
        """Sell `qty` from the first clock >= start_ns until stop_ns; returns (remaining, credits).

        next_bar_vwap: fill at the VWAP of each bar that STARTS at or after the decision (its trades all
        follow the decision), bar by bar under the participation cap, while the bar starts before stop_ns.
        """
        if self.next_bar:
            credits=[];j=bisect.bisect_left(bars.start,start_ns)
            while qty>0 and j<len(bars.start) and bars.start[j]<stop_ns:
                if self.valid_bar(bars,j):
                    q=min(qty,max(0,math.floor(self.p['participation']*bars.volume[j])-used.get(j,0)))
                    if q>0:
                        used[j]=used.get(j,0)+q;qty-=q;at=int(bars.start[j])
                        amount=self.fill(path,'sell',q,bars.vwap[j]);credits.append((amount,due_by_day(self.ny_date(at))))
                        path.events.append(('sell',at,q,float(bars.vwap[j])))
                j+=1
            return qty,credits
        credits=[];clock=start_ns
        while qty>0:
            i=self.ref(bars,clock)
            if i is not None:
                cap=max(0,math.floor(self.p['participation']*bars.volume[i])-used.get(i,0))
                q=min(qty,cap)
                if q>0:
                    used[i]=used.get(i,0)+q;qty-=q
                    amount=self.fill(path,'sell',q,bars.vwap[i]);credits.append((amount,due_by_day(self.ny_date(clock))))
                    path.events.append(('sell',int(clock),q,float(bars.vwap[i])))
            j=bisect.bisect_right(bars.start,clock-MINUTE-self.lag)  # next bar not yet known
            if j>=len(bars.start):break
            clock=int(bars.start[j])+MINUTE+self.lag
            if clock>=stop_ns:break
        return qty,credits

    # ---- one row ----------------------------------------------------------------------------
    def run(self,symbol,signal_ns,exit_ns,target):
        """Isolated path for a decision clock: entry at signal_ns, earliest variant exit at exit_ns."""
        path=Path();bars=self.m.bars.get(symbol);cash=CASH0;receivables=[]
        attempt=signal_ns+self.lag
        reason=self.gate(symbol,attempt,target)
        if reason:  # reference finish_entry: only liquidity/eligibility reasons are observed_unfilled
            path.status='observed_unfilled' if reason in LIQUIDITY else 'input_unresolved';path.reason=reason;return path
        if exit_ns is not None and exit_ns<=attempt:  # reference: strategy_off latches before entries
            path.status='observed_unfilled';path.reason='strategy_off_before_entry';return path
        if not self.covered(bars,attempt):
            path.status='input_unresolved';path.reason='entry_bars_uncaptured';return path
        if self.next_bar:
            # The fill minute is [t, t+60 s): every trade in it follows the decision at signal close t.
            if not self.covered(bars,signal_ns+MINUTE-1):
                path.status='input_unresolved';path.reason='entry_bars_uncaptured';return path
            i=bisect.bisect_left(bars.start,signal_ns)
            if i>=len(bars.start) or bars.start[i]!=signal_ns or not self.valid_bar(bars,i):
                path.status='observed_unfilled';path.reason='next_bar_missing';return path
            attempt=signal_ns+MINUTE+self.lag  # fill known after the fill bar completes
        else:
            i=self.ref(bars,attempt)
            if i is None or attempt>signal_ns+MINUTE:
                path.status='observed_unfilled';path.reason='reference_missing_or_stale';return path
        price=float(bars.vwap[i]);unit=MULT*price*(1+self.cost)
        q=min(math.floor(min(cash/100,.1*CASH0/100)/unit),math.floor(self.p['participation']*bars.volume[i]))
        if q<=0:
            path.status='size_ineligible';path.reason='size_ineligible';return path
        debit=self.fill(path,'buy',q,price);cash-=debit
        path.debit=debit;path.quantity=q;path.entry_vwap=price;path.events.append(('buy',attempt,q,price))
        legs=[(symbol,q,price,{i:q},attempt)];flows=-debit;terminal=attempt
        while legs:
            sym,qty,entry_vwap,used,held_from=legs.pop()
            out=self.hold(path,sym,qty,entry_vwap,used,held_from,exit_ns,target,cash)
            if out is None:return path
            credits,debits,next_leg,last=out
            for amount,due in credits:
                if due is None:
                    path.status='right_censored_end';path.reason='settlement_after_end';return path
                flows+=amount;terminal=max(terminal,due);receivables.append((amount,due))
            for amount,due in debits:flows-=amount;terminal=max(terminal,due)
            terminal=max(terminal,last)
            if next_leg:
                path.rolls+=1
                if path.rolls>60:
                    path.status='input_unresolved';path.reason='roll_limit_logic';return path
                legs.append(next_leg)
        if terminal>=self.end:
            path.status='right_censored_end';path.reason='settlement_or_observation_after_end';return path
        path.status='settled';path.pnl=flows;path.terminal_ns=terminal
        return path

    def hold(self,path,sym,qty,entry_vwap,used,held_from,exit_ns,target,cash):
        """Hold one leg; returns (credits, debits, next roll leg or None, last event ns) or None on terminal failure."""
        bars=self.m.bars[sym];ticker,right,expiry,strike,_=self.m.contracts[sym]
        close=self.expiry_close(expiry);due=self.option_due
        if close is None:return self.hold_past_end(path,bars,used,qty,entry_vwap,held_from,exit_ns)
        cutoff=close-15*MINUTE
        # First stop clock: first bar known after the hold began with VWAP <= 0.875 x entry VWAP.
        k=bisect.bisect_right(bars.start,held_from-MINUTE-self.lag)
        stop_ns=None
        hit=np.flatnonzero(bars.vwap[k:]<=self.p['stop_fraction']*entry_vwap) if self.p['stop_fraction'] else []
        for h in hit:
            at=int(bars.start[k+h])+MINUTE+self.lag
            if at>=close:break
            if self.ref(bars,at)==k+h:stop_ns=at;break
        intent=min(x for x in (stop_ns,exit_ns if exit_ns is not None and exit_ns>held_from else None,math.inf) if x is not None)
        if intent<cutoff:
            if intent>=self.end:path.status='right_censored_end';path.reason='open_at_end';return None
            if bars.hi<min(close,self.end):path.status='input_unresolved';path.reason='held_bars_uncaptured';return None
            path.exit_kind='premium_stop' if intent==stop_ns else 'strategy_exit'
            rest,credits=self.sell(path,bars,used,qty,int(intent),close,due)
            if rest==0:return credits,[],None,latest(credits,int(intent))
            return self.expire(path,sym,rest,credits,None)
        if cutoff>=self.end:path.status='right_censored_end';path.reason='open_at_end';return None
        if bars.hi<close:path.status='input_unresolved';path.reason='held_bars_uncaptured';return None
        # Expiry cutoff: moneyness from a fresh SIP quote midpoint; unknown retains liability.
        qi,why=self.quote(ticker,cutoff)
        if qi is None:path.status='input_unresolved';path.reason='expiry_moneyness_'+why;return None
        qt=self.m.quotes[ticker];spot=(qt.bid[qi]+qt.ask[qi])/2
        itm=spot>strike if right=='call' else spot<strike
        roll=not itm and (exit_ns is None or exit_ns>cutoff)
        path.exit_kind='expiry_itm_sale' if itm else 'expiry_otm_roll' if roll else 'expiry_otm_exit'
        sale_from=cutoff if itm or roll else min(cutoff,exit_ns)
        rest,credits=self.sell(path,bars,used,qty,int(sale_from),close,due)
        if rest:return self.expire(path,sym,rest,credits,None)
        last=latest(credits,cutoff)
        if not roll:return credits,[],None,last
        return self.roll(path,ticker,right,target,credits,[],last,exit_ns)

    def hold_past_end(self,path,bars,used,qty,entry_vwap,held_from,exit_ns):
        """Expiry after the fixed end: observe through the last session close only; no expiry logic."""
        horizon=max(c for _,c in self.m.sessions.values() if c<=self.end)
        if bars.hi<horizon:path.status='input_unresolved';path.reason='held_bars_uncaptured';return None
        k=bisect.bisect_right(bars.start,held_from-MINUTE-self.lag);stop_ns=None
        for h in (np.flatnonzero(bars.vwap[k:]<=self.p['stop_fraction']*entry_vwap) if self.p['stop_fraction'] else []):
            at=int(bars.start[k+h])+MINUTE+self.lag
            if at>=horizon:break
            if self.ref(bars,at)==k+h:stop_ns=at;break
        cands=[x for x in (stop_ns,exit_ns if exit_ns is not None and exit_ns>held_from else None) if x is not None and x<horizon]
        if not cands:path.status='right_censored_end';path.reason='open_at_end';return None
        intent=min(cands);path.exit_kind='premium_stop' if intent==stop_ns else 'strategy_exit'
        rest,credits=self.sell(path,bars,used,qty,int(intent),horizon,self.option_due)
        if rest:path.status='right_censored_end';path.reason='unsold_at_end';return None
        return credits,[],None,latest(credits,int(intent))

    def expire(self,path,sym,qty,credits,_):
        """Unsold quantity at the option close: OCC exercise-by-exception at the official close."""
        ticker,right,expiry,strike,_=self.m.contracts[sym];close=self.expiry_close(expiry)
        ref=self.m.references.get((ticker,self.effective(expiry)))
        if ref is None:path.status='input_unresolved';path.reason='dated_exercise_reference_missing';return None
        from nn_meta.etfe.closing_reference import exercise_outcome
        o=exercise_outcome('C' if right=='call' else 'P',strike,ref);path.pin=path.pin or o['pin']
        last=latest(credits,close)
        if not o['exercised']:
            path.events.append(('nonexercise',close,qty,ref));return credits,[],None,last
        if right=='put':path.status='funding_unresolved';path.reason='put_exercise_without_settled_shares';return None
        due=self.equity_due(self.effective(expiry))
        if due is None:path.status='input_unresolved';path.reason='exercise_settlement_calendar_missing';return None
        strike_cash=cents(qty*MULT*strike)+cents(qty*self.p['exercise_fee'])
        spendable=CASH0-path.spent+sum(a for a,d in path.prior+credits if d is not None and d<=due)
        if strike_cash>spendable:path.status='funding_unresolved';path.reason='exercise_cash_insufficient';return None
        path.events.append(('exercise',close,qty,ref))
        sold,stock_credits,last_sale=self.liquidate(path,ticker,qty*MULT,due)
        if sold is None:return None
        return credits+stock_credits,[(strike_cash,due)],None,max(last,last_sale)

    def liquidate(self,path,ticker,shares,due):
        """Sell delivered shares at fresh SIP bids from settlement + 1 s latency; new quote per retry."""
        q=self.m.quotes.get(ticker);from nn_meta.etfe.dated_policy import quote_size_shares
        if due>=self.end:path.status='right_censored_end';path.reason='delivery_after_end';return None,None,None
        clock=due+NS;credits=[];last=due;seen=-1
        while shares>0:
            i,why=self.quote(ticker,clock,regular_start=True)
            if i is None and why=='quote_uncaptured':
                path.status='input_unresolved';path.reason='liquidation_quotes_exhausted';return None,None,None
            if i is not None and i>seen and q.t[i]>=due:
                seen=i;size=quote_size_shares(int(q.bid_size[i]),self.ny_date(int(q.t[i])))
                sold=min(shares,size);shares-=sold
                gross=float(sold*q.bid[i]);amount=cents(gross-gross*.001*self.cm-gross*.0005*self.cm)
                sale_due=self.equity_due(self.ny_date(clock))
                if sale_due is None:path.status='input_unresolved';path.reason='stock_settlement_calendar_missing';return None,None,None
                credits.append((amount,sale_due));last=max(last,sale_due);path.events.append(('stock_sell',clock,sold,float(q.bid[i])))
            if shares==0:break  # sold out on the last captured quote: complete, not exhausted
            nxt=bisect.bisect_right(q.t,clock-self.qlag)
            if nxt>=len(q.t):path.status='input_unresolved';path.reason='liquidation_quotes_exhausted';return None,None,None
            clock=max(clock+1,int(q.t[nxt])+self.qlag)
        return True,credits,last

    def roll(self,path,ticker,right,target,credits,debits,last,exit_ns):
        """Begin a roll at each regular minute M >= settlement of the old-leg sale while the row is on.

        Selection uses the SIP midpoint known at M; the purchase uses the bar ending at M at M+lag.
        Quotes exist only where captured; the first minute after the open has no regular quote yet.
        """
        budget=sum(a for a,_ in credits)
        if budget<=0:return credits,debits,None,last
        if any(d is None for _,d in credits):return credits,debits,None,last  # censored in run()
        clock=max(d for _,d in credits)
        while True:
            if exit_ns is not None and clock>=exit_ns:return credits,debits,None,last
            if clock>=self.end:path.status='right_censored_end';path.reason='roll_pending_at_end';return None
            day=self.ny_date(clock);s=self.m.sessions.get(day)
            if s is None or not s[0]<=clock<s[1]:
                later=[d for d in self.m.sessions if d>day]
                if not later:path.status='right_censored_end';path.reason='roll_pending_at_end';return None
                clock=self.m.sessions[min(later)][0];continue
            if clock-self.qlag<s[0]:clock+=MINUTE;continue  # no regular quote known yet
            qi,why=self.quote(ticker,clock,regular_start=True)
            if qi is None:path.status='input_unresolved';path.reason='roll_'+why;return None
            qt=self.m.quotes[ticker];spot=(qt.bid[qi]+qt.ask[qi])/2
            sym=self.select_roll(ticker,right,target,clock,spot)
            if sym is not None:
                bars=self.m.bars.get(sym);attempt=clock+self.lag
                if not self.covered(bars,attempt):path.status='input_unresolved';path.reason='roll_leg_bars_uncaptured';return None
                if self.next_bar:  # fill minute [M, M+60 s) follows the roll decision at M
                    i=bisect.bisect_left(bars.start,clock)
                    i=i if i<len(bars.start) and bars.start[i]==clock and self.valid_bar(bars,i) else None
                    attempt=clock+MINUTE+self.lag
                else:i=self.ref(bars,attempt)
                if i is not None:
                    price=float(bars.vwap[i]);unit=MULT*price*(1+self.cost)
                    q=min(math.floor(budget/100/unit),math.floor(self.p['participation']*bars.volume[i]))
                    if q>0:
                        amount=self.fill(path,'buy',q,price);path.events.append(('roll_buy',attempt,q,price))
                        path.prior.extend(credits)
                        return credits,debits+[(amount,attempt)],(sym,q,price,{i:q},attempt),max(last,attempt)
            clock+=MINUTE

    def select_roll(self,ticker,right,target,clock,spot):
        """Reference `_select_roll` order: (|dte-target|, expiry, |strike-spot|, strike, contract)."""
        day=self.ny_date(clock);best=None
        for off in range(6):
            e=date.fromordinal(day.toordinal()+off)
            for strike,sym in self.m.by_expiry.get((ticker,right,e),()):
                if not .85*spot<=strike<=1.15*spot or self.gate(sym,clock+self.lag,target):continue
                key=(abs(off-target),e,abs(strike-spot),strike,sym)
                if best is None or key<best:best=key
        return None if best is None else best[-1]
