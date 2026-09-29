"""Per-security, bounded-memory consumer of every factorized execution horizon."""
from functools import lru_cache
import json
from pathlib import Path
import sqlite3

import pandas as pd

from nn_meta.v7.chain import ObservedChain
from nn_meta.v7.execution import CaptureUnavailable
from nn_meta.v7.execution_frontier_v2 import discover_execution
from nn_meta.v7.replay_clocks import ReplayClocks
from nn_meta.v7.entry_demand import selection_id
from nn_meta.v7.storage import sha,verify,identity


class ExecutionWorker:
    def __init__(self, demand, archive, references, hours):
        self.root=Path(demand).resolve()
        header=verify(self.root)
        self.declaration=json.loads((self.root/'declaration.json').read_text())
        self.inputs={str(self.root/'complete.json'):sha(self.root/'complete.json')}
        self.inputs.update({str(self.root/n):h for n,h in header['files'].items()})
        store=Path(self.declaration['proposal_stores'][0])
        for directory in [store/'declaration',store/'summary']:
            anchor=str(directory/'complete.json')
            if sha(anchor)!=self.declaration['inputs'][anchor]:raise ValueError('Proposal source changed')
            verify(directory);self.inputs[anchor]=sha(anchor)
        self.proposal_declaration=json.loads((store/'declaration/declaration.json').read_text())
        feature=Path(self.proposal_declaration['feature_store'])
        for directory in [feature/'basis',Path(self.declaration['chain']).parent]:
            anchor=str(directory/'complete.json')
            if sha(anchor)!=self.declaration['inputs'][anchor]:raise ValueError('Execution basis/chain changed')
            verify(directory);self.inputs[anchor]=sha(anchor)
        self.raw=pd.read_parquet(feature/'basis/raw.parquet',columns=['Close','available_at'])
        self.available=pd.DatetimeIndex(self.raw.available_at)
        if self.available.has_duplicates or not self.available.is_monotonic_increasing:
            raise ValueError('Raw availability clocks are unordered')
        self.db=sqlite3.connect((self.root/'demand.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True)
        self.db.execute('PRAGMA cache_size=-2048')
        self.archive,self.references,self.hours=archive,references,hours

    @lru_cache(maxsize=2)
    def chain(self,symbol):
        return ObservedChain(self.declaration['chain'],symbol)

    @lru_cache(maxsize=4096)
    def select(self,symbol,right,target,clock):
        stamp=pd.Timestamp(clock,unit='ns',tz='UTC')
        day=stamp.tz_convert('America/New_York').date()
        routing=self.proposal_declaration['symbols_by_date']
        if routing is not None and routing.get(day.isoformat())!=symbol:
            raise CaptureUnavailable('Held ticker/lifecycle boundary')
        pos=self.available.searchsorted(stamp,side='right')-1
        if pos<0 or not 0<=clock-self.available[pos].value<=60_000_000_000:return None
        row=self.chain(symbol).select(day,float(self.raw.Close.iloc[pos]),right,target)
        return row['ticker'].removeprefix('O:') if row else None

    @lru_cache(maxsize=2)
    def clocks(self,symbol):
        def values():
            for day in self.hours.days:
                if self.declaration['start']<=day<=self.declaration['end']:
                    session=self.hours.at(symbol,day)
                    yield from range(session['open_ns']+60_000_000_000,session['close_ns']+1,60_000_000_000)
        return ReplayClocks(values())

    def run(self,proposal,target):
        key=selection_id(proposal['symbol'],proposal['decision_ns'],proposal['right'],target)
        selected=self.db.execute('SELECT status,contract FROM selections WHERE selection_id=?',(key,)).fetchone()
        if selected is None:raise ValueError('Execution horizon lacks frozen selection')
        status,contract=selected
        if status!='selected':
            return dict(status=status,selection_id=key,contract=contract,pending=[],label_complete=False,
                        disposition='no_selected_contract',research_ready=False)
        chosen=self.select(proposal['symbol'],proposal['right'],target,proposal['decision_ns'])
        if chosen!=contract:raise ValueError('Execution selector differs from frozen entry demand')
        result=discover_execution(proposal,self.clocks(proposal['symbol']).after(proposal['decision_ns']),
            self.archive,self.references,self.hours,
            select_contract=lambda clock:self.select(proposal['symbol'],proposal['right'],target,clock))
        result.update(status=result['replay']['status'],selection_id=key,contract=contract,
                      label_complete=result['replay']['label_complete'])
        return result

    def close(self):
        self.chain.cache_clear();self.clocks.cache_clear();self.select.cache_clear();self.db.close()


def build_security_quote_index(demand,base_index,entry_root,output):
    """Reuse the complete security's entry packs and relevant retained frontier packs."""
    from nn_meta.v7.packed_quote_index import write_index
    demand,base_index,entry_root,output=map(Path,(demand,base_index,entry_root,output))
    verify(demand);verify(base_index)
    declaration=json.loads((demand/'declaration.json').read_text())
    sid=declaration['security_id'];digest=sha(demand/'complete.json')
    with sqlite3.connect((demand/'demand.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as db:
        roots=[r[0].replace('.','') for r in db.execute('SELECT DISTINCT symbol FROM decisions')]
    packs={}
    with sqlite3.connect((base_index/'index.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as db:
        for symbol in roots:
            for path,anchor in db.execute('SELECT DISTINCT p.path,p.receipt_sha256 FROM packs p JOIN ranges r ON r.pack=p.id WHERE r.contract GLOB ?', (symbol+'[0-9]*',)):
                packs[str(Path(path).resolve())]=anchor
    for head in sorted((entry_root/sid).glob('*/complete.json')):
        pack=head.parent.resolve()
        header=json.loads(head.read_text());binding=json.loads((pack/'binding.json').read_text())
        if (header['identity']!=identity(binding) or binding['source']['security_id']!=sid
                or binding['source']['receipt_sha256']!=digest):
            raise ValueError('Entry pack belongs to another frozen demand')
        packs[str(pack)]=sha(head)
    if not packs:raise ValueError('No completed capture packs for selected security')
    binding=dict(schema='v7-full-security-quote-index-v1',security_id=sid,
        demand_sha256=digest,base_index_sha256=sha(base_index/'complete.json'),packs=packs,
        producer_sha256=sha(__file__))
    if output.exists():verify(output,expected_identity=identity(binding))
    else:write_index(output,sorted(packs),binding=binding)
    for path,anchor in packs.items():
        if sha(Path(path)/'complete.json')!=anchor:raise ValueError('Indexed capture changed')
    return output
