#!/usr/bin/env python3
"""Seal bounded exact missing tick windows from a stopped full-queue checkpoint."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['wave','security','previous-index','output']:
        p.add_argument('--'+name,required=True,type=str if name=='security' else Path)
    a=p.parse_args()
    from nn_meta.v7.storage import verify,sha,identity,receipt,transaction
    from nn_meta.v7.quotes import capture_union
    from nn_meta.v7.packed_quote_index import IndexedQuoteArchive
    root=a.wave.resolve()/'securities'/a.security;index=a.wave.resolve()/'indexes'/a.security
    status=json.loads((root/'progress.json').read_text())
    if status['status'] not in ['checkpointed','discovered']:raise ValueError('Stopped wave checkpoint required')
    parent=json.loads((a.wave/'declaration.json').read_text())
    inputs=dict(parent['inputs']);inputs.update(json.loads((root/'consumed-inputs.json').read_text()))
    for path in [Path(__file__),root/'wave.sqlite3',root/'binding.json',a.wave/'declaration.json',index/'complete.json',a.previous_index.resolve()/'complete.json']:
        inputs[str(path.resolve())]=sha(path)
    verify(index);verify(a.previous_index)
    with sqlite3.connect((root/'wave.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        requests=[json.loads(row[0]) for row in db.execute('SELECT request FROM pending')]
    windows=[]
    with IndexedQuoteArchive(index) as archive:
        for request in sorted(requests,key=lambda r:r['request_id']):
            if request['provider']!='massive' or request['kind'] not in ('quotes','trades'):continue
            cursor=request['start_ns'];end=request['end_ns']
            for lo,hi in archive.db.execute('SELECT start_ns,end_ns FROM ranges WHERE contract=? AND kind=? AND start_ns<? AND end_ns>? ORDER BY start_ns',
                (request['contract'],request['kind'],end,cursor)):
                if lo>cursor:
                    scope=dict(contract=request['contract'],kind=request['kind'],start_ns=cursor,end_ns=min(lo,end))
                    windows.append(dict(scope,request_id=identity(scope)))
                cursor=max(cursor,min(hi,end))
            if cursor<end:
                scope=dict(contract=request['contract'],kind=request['kind'],start_ns=cursor,end_ns=end)
                windows.append(dict(scope,request_id=identity(scope)))
    union=capture_union(windows,max_span_ns=86400*10**9)
    selected=[];duration=0
    for capture in union['captures']:
        size=capture['end_ns']-capture['start_ns']
        if len(selected)>=128 or duration+size>3600*10**9:break
        scope={k:capture[k] for k in ('contract','kind','start_ns','end_ns')}
        selected.append(dict(scope,request_id=identity(scope)));duration+=size
    if not selected:raise ValueError('No bounded missing tick windows')
    if any(sha(path)!=digest for path,digest in inputs.items()):raise ValueError('Wave checkpoint changed')
    binding=dict(schema='v7-full-wave-frontier-export-v1',inputs=inputs,security_id=a.security)
    report=dict(actual_pending_requests=len(requests),union_windows=len(union['captures']),selected_windows=len(selected),
                selected_seconds=duration/1e9,full_execution_coverage=False,research_ready=False)
    with transaction(a.output) as temp:
        for name,doc in [('binding.json',binding),('report.json',report),('capture-requests.json',selected)]:
            (temp/name).write_text(json.dumps(doc,sort_keys=True,indent=2)+'\n')
        receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps(report))


if __name__=='__main__':main()
