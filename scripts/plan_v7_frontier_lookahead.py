#!/usr/bin/env python3
"""Plan bounded same-session quote prefetch from actual unresolved replay reads.

Prefetch is acquisition overhead, not proof that a path consumes every quote.
No reference, identity, expiry or session boundary is crossed by this planner.
"""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def uncovered(db,contract,start,end):
    cursor=start
    for lo,hi in db.execute('SELECT start_ns,end_ns FROM ranges WHERE contract=? AND kind="quotes" AND start_ns<? AND end_ns>? ORDER BY start_ns',(contract,end,start)):
        if lo>cursor:yield cursor,min(lo,end)
        cursor=max(cursor,min(hi,end))
    if cursor<end:yield cursor,end


def plan(cases,archive,hours,minutes):
    import pandas as pd
    from options.data.provider import parse_occ_symbol
    from nn_meta.v7.storage import identity
    if type(minutes) is not int or not 1<=minutes<=10:raise ValueError('One to ten minutes per frontier required')
    captures={};expansions=[]
    for case in cases:
        for request in case['pending']:
            if request['provider']!='massive' or request['kind']!='quotes':continue
            contract=request['contract'];root,expiry,_,_=parse_occ_symbol(contract)
            start=request['start_ns'];day=pd.Timestamp(start,unit='ns',tz='UTC').tz_convert('America/New_York').date().isoformat()
            session=hours.at(root,day)
            if not session['open_ns']<=start<request['end_ns']<=session['close_ns'] or day>expiry.isoformat():
                raise ValueError('Actual read is outside captured dated session/expiry')
            end=min(session['close_ns'],max(request['end_ns'],start+minutes*60*10**9))
            expansions.append(dict(frontier_request_id=request['request_id'],contract=contract,date=day,
                required_start_ns=start,required_end_ns=request['end_ns'],prefetch_end_ns=end))
            for lo,hi in uncovered(archive.db,contract,start,end):
                scope=dict(contract=contract,kind='quotes',start_ns=lo,end_ns=hi)
                captures[identity(scope)]=dict(scope,request_id=identity(scope))
    # The current bounded proof has one path per contract. Reject overlapping
    # prefetch from different paths rather than hide acquisition double counting.
    ordered=sorted(captures.values(),key=lambda r:(r['contract'],r['start_ns']))
    for a,b in zip(ordered,ordered[1:]):
        if a['contract']==b['contract'] and a['end_ns']>b['start_ns']:raise ValueError('Overlapping prefetch paths require union planning')
    if not ordered or len(ordered)>128 or sum(r['end_ns']-r['start_ns'] for r in ordered)>3600*10**9:
        raise ValueError('Nonempty prefetch limited to 128 ranges / one quote hour')
    return ordered,expansions


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('frontier','quotes','hours','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--minutes',type=int,default=10);a=p.parse_args()
    from nn_meta.v7.storage import verify,sha,identity,transaction,receipt
    from nn_meta.v7.dated_hours import DatedHours
    from nn_meta.v7.packed_quote_index import IndexedQuoteArchive
    for key in ('frontier','quotes','hours','output'):setattr(a,key,getattr(a,key).resolve())
    if not a.output.is_relative_to(ROOT/'nn_meta/validation'):p.error('Use a new validation output')
    verify(a.frontier);verify(a.quotes);hours=DatedHours(a.hours)
    inputs=json.loads((a.frontier/'binding.json').read_text())['inputs']
    if inputs.get(str(a.quotes/'complete.json'))!=sha(a.quotes/'complete.json'):raise ValueError('Wrong frontier index')
    inputs.update(hours.inputs)
    for f in (a.frontier/'complete.json',a.frontier/'report.json',Path(__file__)):inputs[str(f)]=sha(f)
    if any(sha(f)!=h for f,h in inputs.items()):raise ValueError('Prefetch source changed')
    with IndexedQuoteArchive(a.quotes) as archive:
        requests,expansions=plan(json.loads((a.frontier/'report.json').read_text())['cases'],archive,hours,a.minutes)
    binding=dict(schema='v7-bounded-frontier-prefetch-v1',inputs=inputs,minutes=a.minutes)
    report=dict(schema=binding['schema'],expansions=expansions,requests=len(requests),
        acquisition_quote_ns=sum(r['end_ns']-r['start_ns'] for r in requests),
        prefetch_is_actual_path_demand=False,full_execution_coverage=False,research_ready=False)
    if a.output.exists():verify(a.output,expected_identity=identity(binding))
    else:
        with transaction(a.output) as temp:
            for name,doc in [('binding.json',binding),('report.json',report),('capture-requests.json',requests)]:
                (temp/name).write_text(json.dumps(doc,sort_keys=True,indent=2)+'\n')
            receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps(report))


if __name__=='__main__':main()
