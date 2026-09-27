#!/usr/bin/env python3
"""Replay five existing source-bound purchase cases to their next real data gap.

Uses immutable indexed packs and exact frozen proposal horizons. This bounded
consumer proof is not a full campaign or a physical-delivery implementation.
"""
import argparse
from bisect import bisect_left
import io
import json
from pathlib import Path
import sqlite3
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hours',type=Path,required=True);p.add_argument('--blackouts',type=Path,required=True)
    p.add_argument('--quotes',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cases',type=Path,default=ROOT/'nn_meta/validation/v7-direct-packed-fill-requests-20260927.json')
    p.add_argument('--references',type=Path,default=ROOT/'nn_meta/data_v7/entry-joined-sample-references-20260926')
    args=p.parse_args()
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    import pyarrow.parquet as pq
    from nn_meta.v7.storage import identity,sha,verify,receipt,transaction
    from nn_meta.v7.dated_hours import DatedHours,MINUTE
    from nn_meta.v7.contract_blackouts import BlackoutPolicy,BlackoutReferences
    from nn_meta.v7.contracts import ContractReferences
    from nn_meta.v7.compact_proposals import read_proposals
    from nn_meta.v7.chain import ObservedChain
    from nn_meta.v7.packed_quote_index import IndexedQuoteArchive
    from nn_meta.v7.execution_frontier import discover_execution
    from nn_meta.v7.execution import CaptureUnavailable
    for key in vars(args):setattr(args,key,getattr(args,key).resolve())
    if not args.output.is_relative_to(ROOT/'nn_meta/validation'):p.error('Use new validation output')
    hours=DatedHours(args.hours);policy=BlackoutPolicy(args.blackouts)
    inputs=dict(hours.inputs);inputs.update(policy.inputs)
    for file in (Path(__file__),args.cases,ROOT/'nn_meta/v7/execution_frontier.py',ROOT/'nn_meta/v7/replay.py',
                 ROOT/'nn_meta/v7/chain.py',ROOT/'nn_meta/v7/compact_proposals.py',
                 ROOT/'nn_meta/v7/execution.py',ROOT/'nn_meta/v7/quote_archive.py',
                 ROOT/'nn_meta/v7/contracts.py',ROOT/'options/paper_pricing.py',ROOT/'options/paper_risk.py'):
        inputs[str(file)]=sha(file)
    def bind(path):
        path=Path(path).resolve();header=verify(path)
        inputs[str(path/'complete.json')]=sha(path/'complete.json')
        inputs.update({str(path/n):h for n,h in header['files'].items()})
        return header
    bind(args.quotes)
    results=[]
    with IndexedQuoteArchive(args.quotes) as archive:
        for path,digest in archive.db.execute('SELECT path,receipt_sha256 FROM packs'):
            if sha(Path(path)/'complete.json')!=digest:raise ValueError('Packed source changed')
            bind(path)
        for anchor in json.loads(args.cases.read_text()):
            parent=Path(anchor['demand_receipt']).parent
            if sha(parent/'complete.json')!=anchor['demand_receipt_sha256']:raise ValueError('Frozen sample parent changed')
            bind(parent);declaration=json.loads((parent/'declaration.json').read_text())
            for path,digest in declaration['inputs'].items():
                if path in inputs and inputs[path]!=digest:raise ValueError('Conflicting frozen discovery inputs')
                inputs[path]=digest
            clock=anchor['decision_ns'];contract=anchor['contract']
            with sqlite3.connect((parent/'demand.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
                symbol,right,target=db.execute('SELECT symbol,right,target_dte FROM selections WHERE contract=? AND decision_ns=? AND status="selected" ORDER BY target_dte LIMIT 1',(contract,clock)).fetchone()
            proposal=None;chosen_store=None
            # Filter actual compact rows, then use the unchanged canonical decoder.
            for store_text in declaration['proposal_stores']:
                store=Path(store_text);bind(store/'declaration');bind(store/'summary')
                doc=json.loads((store/'declaration/declaration.json').read_text())
                summary=json.loads((store/'summary/report.json').read_text())
                for part in summary['batches']:
                    directory=store/'batches'/str(part['batch'])
                    if sha(directory/'complete.json')!=part['receipt_sha256']:raise ValueError('Proposal batch changed')
                    # Only matched batches are bound as row sources; footer filtering
                    # never changes the original file or its dictionary metadata.
                    table=pq.read_table(directory/'proposals.parquet',filters=[('decision_ns','=',clock),('is_put','=',right=='P'),('symbol','=',symbol)])
                    if not table.num_rows:continue
                    bind(directory)
                    buf=io.BytesIO();pq.write_table(table.slice(0,1),buf);buf.seek(0)
                    proposal=next(read_proposals(buf,doc));chosen_store=doc
                    break
                if proposal is not None:break
            if proposal is None:raise ValueError('Frozen selected decision lacks original proposal')
            feature=Path(chosen_store['feature_store']);bind(feature/'declaration');bind(feature/'basis')
            raw=pd.read_parquet(feature/'basis/raw.parquet');available=pd.DatetimeIndex(raw.available_at)
            if available.has_duplicates or not available.is_monotonic_increasing:raise ValueError('Unordered raw causal basis')
            chain_path=Path(declaration['chain']);bind(chain_path.parent)
            chain=ObservedChain(chain_path,symbol)
            route=chosen_store['symbols_by_date']
            def select(t):
                stamp=pd.Timestamp(t,unit='ns',tz='UTC');day=stamp.tz_convert('America/New_York').date().isoformat()
                if route is not None and route.get(day)!=symbol:raise CaptureUnavailable('Held ticker/lifecycle boundary')
                pos=available.searchsorted(stamp,side='right')-1
                if pos<0 or not 0<=t-available[pos].value<=MINUTE:return None
                result=chain.select(stamp.tz_convert('America/New_York').date(),float(raw.Close.iloc[pos]),right,target)
                return result['ticker'].removeprefix('O:') if result else None
            if select(clock)!=contract:raise ValueError('Current exact selector differs from frozen selection')
            clocks=[]
            for day in hours.days:
                if chosen_store['start']<=day<=chosen_store['end']:
                    s=hours.at(symbol,day);clocks.extend(range(s['open_ns']+MINUTE,s['close_ns']+1,MINUTE))
            references=BlackoutReferences(ContractReferences(args.references),policy)
            result=discover_execution(proposal,clocks[bisect_left(clocks,clock):],archive,references,hours,select_contract=select)
            result.update(target_dte=target,security_id=declaration['security_id'],source_proposal=proposal)
            for request in result['observed_inputs']:
                if request['kind']=='contract_reference':bind(args.references/request['contract']/request['date'])
            results.append(result)
            print(json.dumps(dict(symbol=symbol,status=result['replay']['status'],fills=len(result['replay']['fills']),pending=len(result['pending']))),flush=True)
        pending={r['request_id']:r for result in results for r in result['pending']}
        captures=[]
        for request in pending.values():
            if request['provider']!='massive' or request['kind'] not in ('quotes','trades'):continue
            # Request only the still-missing portions of an actual consumer read.
            cursor=request['start_ns'];end=request['end_ns']
            for lo,hi in archive.db.execute('SELECT start_ns,end_ns FROM ranges WHERE contract=? AND kind=? AND start_ns<? AND end_ns>? ORDER BY start_ns',
                 (request['contract'],request['kind'],end,cursor)):
                if lo>cursor:
                    scope=dict(contract=request['contract'],kind=request['kind'],start_ns=cursor,end_ns=min(lo,end))
                    captures.append(dict(scope,request_id=identity(scope),frontier_request_id=request['request_id']))
                cursor=max(cursor,min(hi,end))
            if cursor<end:
                scope=dict(contract=request['contract'],kind=request['kind'],start_ns=cursor,end_ns=end)
                captures.append(dict(scope,request_id=identity(scope),frontier_request_id=request['request_id']))
    binding=dict(inputs=inputs)
    if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Execution discovery source changed')
    report=dict(schema='v7-execution-discovery-proof-v1',cases=results,paths=len(results),
        complete_labels=sum(r['replay']['label_complete'] for r in results),pending=list(pending.values()),
        full_execution_coverage=False,research_ready=False)
    if args.output.exists():verify(args.output,expected_identity=identity(binding))
    else:
        with transaction(args.output) as temp:
            for name,doc in [('binding.json',binding),('report.json',report),('capture-requests.json',captures)]:
                (temp/name).write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
            receipt(temp,dict(identity=identity(binding),research_ready=False))


if __name__=='__main__':main()
