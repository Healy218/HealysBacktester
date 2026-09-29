"""Versioned full-queue frontier using reusable validated replay clocks.

A missing mark latches the path closed to further reads: replay may retain its
partial ledger, but no later branch is explored using an unknown earlier mark.
Restart from immutable inputs after capture; completed sparse markets still
return genuine unfilled/stale outcomes. No downloads happen here.
"""
from copy import deepcopy
from datetime import datetime
import pandas as pd

from nn_meta.v7.execution import CaptureUnavailable,QuotePolicy
from nn_meta.v7.quote_archive import QuoteArchive
from nn_meta.v7.storage import identity
from nn_meta.v7.contract_blackouts import ReferenceBlackout


class Frontier:
    def __init__(self):
        self.requests={};self.observed={};self.blocked=None;self.blackout=None

    def check(self):
        if self.blocked is not None:raise CaptureUnavailable('Replay awaits its first missing input')

    def read(self,request,call):
        self.check()
        key=identity(request)
        try:
            result=call()
        except ReferenceBlackout as exc:
            self.blackout=deepcopy(exc.treatment);self.blocked='approved_blackout'
            raise
        except (CaptureUnavailable,FileNotFoundError) as exc:
            self.requests[key]=dict(request,request_id=key)
            self.blocked=key
            raise CaptureUnavailable('Uncaptured execution input '+key) from exc
        self.observed[key]=request
        return result


class _Archive(QuoteArchive):
    def __init__(self,parent,frontier):
        self.parent,self.frontier=parent,frontier
        self.policy=parent.policy
        self.purpose='held_mark';self.buys=0

    def window(self,contract,kind,start_ns,end_ns):
        request=dict(provider='massive',kind=kind,contract=contract.removeprefix('O:'),
                     start_ns=int(start_ns),end_ns=int(end_ns),purpose=self.purpose)
        return self.frontier.read(request,lambda:self.parent.window(contract,kind,start_ns,end_ns))

    def first_fill(self,contract,decision_ns,*,side,deadline_ns=None):
        self.purpose=('entry_purchase' if self.buys==0 else 'roll_purchase') if side=='buy' else 'exit_sale'
        result=super().first_fill(contract,decision_ns,side=side,deadline_ns=deadline_ns)
        if side=='buy':self.buys+=1
        return result

    def mark(self,contract,clock_ns):
        self.purpose='held_mark'
        return super().mark(contract,clock_ns)


class _References:
    def __init__(self,parent,frontier):self.parent,self.frontier=parent,frontier
    def standard(self,contract,day):
        return self.frontier.read(dict(provider='massive',kind='contract_reference',
            contract=contract.removeprefix('O:'),date=day),lambda:self.parent.standard(contract,day))


def discover_execution(proposal,clocks,archive,references,sessions,*,select_contract,underlying_mark=None,max_rolls=60):
    """Actual one-path replay with one unresolved frontier; original result retained."""
    from nn_meta.v7.replay_stream import replay
    frontier=Frontier();wrapped=_Archive(archive,frontier)
    def close(clock):
        day=pd.Timestamp(clock,unit='ns',tz='UTC').tz_convert('America/New_York').date().isoformat()
        return frontier.read(dict(provider='exchange',kind='dated_hours',symbol=proposal['symbol'],date=day),
                             lambda:sessions.at(proposal['symbol'],day))['close_ns']
    def cutoff(contract):
        from options.data.provider import parse_occ_symbol
        root,expiry,_,_=parse_occ_symbol(contract)
        return frontier.read(dict(provider='exchange',kind='expiry_hours',symbol=root,date=expiry.isoformat()),
                             lambda:sessions.cutoff(contract))
    def stock(symbol,clock):
        def read():
            if underlying_mark is None:raise CaptureUnavailable('Observed stock midpoint required')
            return underlying_mark(symbol,clock)
        return frontier.read(dict(provider='alpaca',kind='stock_quotes',symbol=symbol,
            start_ns=max(0,clock-archive.policy.max_mark_age_ns),end_ns=clock+1,purpose='expiry_itm_classification'),read)
    result=replay(proposal,clocks,wrapped,_References(references,frontier),select_contract=select_contract,
                  expiry_cutoff=cutoff,session_close=close,underlying_mark=stock,max_rolls=max_rolls,
                  policy=archive.policy)
    if frontier.blocked is not None and (result['label_complete'] or result['net_return'] is not None):
        raise ValueError('Unresolved frontier produced a label')
    if frontier.blackout is not None:
        result=dict(result,status='excluded_contract_reference_blackout',blackout=frontier.blackout)
    return dict(schema='v7-execution-frontier-v1',proposal_id=proposal['proposal_id'],replay=result,
                pending=list(frontier.requests.values()),observed_inputs=list(frontier.observed.values()),
                complete_frontier=frontier.blocked is None,physical_fallback_complete=False,
                full_execution_coverage=False,research_ready=False)
