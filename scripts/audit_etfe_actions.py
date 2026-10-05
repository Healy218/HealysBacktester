"""Independently reconcile normalized ETFE actions to every raw occurrence."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from collections import Counter
import pandas as pd
from nn_meta.etfe.acquisition import digest,sha,save
from nn_meta.etfe.action_capture import verify,URL,STREAM


def audit(root):
    root=Path(root);plan=verify(root);normal=json.loads((root/'NORMALIZED.json').read_text())
    assert normal['plan_sha256']==plan['sha256']
    payload=root/normal['files'][0]['path'];assert sha(payload.read_bytes())==normal['files'][0]['sha256']
    frame=pd.read_parquet(payload);expected=[];counts=Counter();probes=[];page_count=0
    for job in plan['jobs']:
        paths=sorted((root/'jobs'/job['id']).glob('page-*.json'));assert paths
        token=None;seen=set();terminal=False
        for page,path in enumerate(paths):
            assert not terminal and path.name==f'page-{page:06d}.json'
            pointer=json.loads(path.read_text());attempt=root/pointer['attempt']
            assert attempt.resolve().is_relative_to(root.resolve())
            receipt=json.loads((attempt/'receipt.json').read_text());raw=(attempt/'body').read_bytes()
            assert sha((attempt/'receipt.json').read_bytes())==pointer['receipt_sha256'] and sha(raw)==receipt['body_sha256']
            params=dict(job['params'])
            if token is not None:params['page_token']=token
            assert receipt['params']==params and receipt['plan_sha256']==plan['sha256'] and receipt['kind']==job['kind']
            assert receipt['url']==(URL if job['kind']=='actions' else STREAM)
            assert pd.Timestamp(receipt['observed_at'])<=pd.Timestamp(receipt['received_at'])
            if job['kind']=='events_probe':
                terminal=True;probes.append(dict(params=params,status=receipt['status'],error=receipt['error'],
                    bytes=len(raw),content_type=receipt['headers'].get('content-type'),attempt=pointer['attempt'],
                    replay_coverage_verified=False));continue
            assert receipt['status']==200 and receipt['error'] is None;body=json.loads(raw);page_count+=1
            groups=body['corporate_actions'] or {};assert isinstance(groups,dict)
            for group,rows in groups.items():
                for ordinal,row in enumerate(rows):
                    assert job['params']['symbols'] in [v for k,v in row.items() if k=='symbol' or k.endswith('_symbol')]
                    if row.get('process_date') is not None:assert params['start']<=row['process_date']<=params['end']
                    counts[(job['params']['symbols'],group)]+=1
                    expected.append(dict(occurrence_id=digest([job['id'],page,group,ordinal]),query_symbol=params['symbols'],
                        action_type=group,native_id=str(row['id']),process_date=row.get('process_date'),effective_date=row.get('ex_date') or row.get('effective_date'),
                        observed_at=receipt['received_at'],historical_available_at_ns=-1,model_feature_admitted=False,job_id=job['id'],page=page,
                        group_ordinal=ordinal,attempt=pointer['attempt'],body_sha256=sha(raw),raw_json=json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)))
            token=body['next_page_token'];terminal=token is None
            if token is not None:assert isinstance(token,str) and token and token not in seen
            seen.add(token)
        assert terminal
    pd.testing.assert_frame_equal(frame,pd.DataFrame(expected),check_exact=True)
    assert frame.occurrence_id.is_unique and len(frame)==normal['rows']
    assert frame.historical_available_at_ns.eq(-1).all() and not frame.model_feature_admitted.any()
    duplicates=frame.duplicated(['query_symbol','native_id']).sum();conflicts=0
    for _,group in frame.groupby(['query_symbol','native_id']):conflicts+=int(group.raw_json.nunique()>1)
    assert int(duplicates)==normal['duplicate_native_ids']
    result=dict(plan_sha256=plan['sha256'],normalized_sha256=sha((root/'NORMALIZED.json').read_bytes()),
        rows=len(frame),pages=page_count,occurrences_exact=True,rows_by_symbol_type=[dict(symbol=s,kind=k,rows=v) for (s,k),v in sorted(counts.items())],
        duplicate_native_ids=int(duplicates),conflicting_native_ids=conflicts,probes=probes,
        historical_available_fields_present=sorted({k for raw in frame.raw_json for k in json.loads(raw) if any(x in k for x in ('created','updated','published','announc','declar'))}),
        historical_availability_verified=False,complete_effective_date_history=False,model_feature_admitted=False)
    save(root/'INDEPENDENT_AUDIT.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    print(json.dumps(audit(p.parse_args().root),indent=2))
