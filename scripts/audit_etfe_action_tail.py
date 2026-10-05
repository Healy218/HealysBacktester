"""Independent raw REST and line-oriented SSE reconciliation of action-tail evidence."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pandas as pd
from nn_meta.etfe.acquisition import sha,save
from nn_meta.etfe.action_evidence import verify,PARENT


def audit(root):
    root=Path(root);plan=verify(root);report=json.loads((root/'INSPECTION.json').read_text())
    payload=root/report['files'][0]['path'];assert sha(payload.read_bytes())==report['files'][0]['sha256']
    out=json.loads(payload.read_text());tail=[];mutations=[];all_events=0
    for item in plan['jobs']:
        token=None;seen=set();terminal=False
        paths=sorted((root/'jobs'/item['id']).glob('page-*.json'));assert paths
        for page,p in enumerate(paths):
            assert not terminal and p.name==f'page-{page:06d}.json'
            pointer=json.loads(p.read_text());folder=root/pointer['attempt'];receipt=json.loads((folder/'receipt.json').read_text());raw=(folder/'body').read_bytes()
            assert sha((folder/'receipt.json').read_bytes())==pointer['receipt_sha256'] and sha(raw)==receipt['body_sha256']
            assert receipt['plan_sha256']==plan['sha256'] and receipt['status']==200 and receipt['error'] is None
            params=dict(item['params'])
            if token is not None:params['page_token']=token
            assert params==receipt['params'];body=json.loads(raw)
            for kind,rows in (body['corporate_actions'] or {}).items():
                for ordinal,row in enumerate(rows):
                    assert params['symbols']==row['symbol'] and params['start']<=row['process_date']<=params['end']
                    tail.append(dict(symbol=params['symbols'],native_id=row['id'],kind=kind,process_date=row.get('process_date'),effective_date=row.get('ex_date') or row.get('effective_date'),job_id=item['id'],page=page,group_ordinal=ordinal,body_sha256=sha(raw),attempt=pointer['attempt'],raw=row,historical_available_at_ns=-1,model_feature_admitted=False))
            token=body['next_page_token'];terminal=token is None
            if token is not None:assert token not in seen
            seen.add(token)
        assert terminal
    for probe in report['probes']:
        folder=PARENT/probe['attempt'];raw=(folder/'body').read_bytes();receipt=json.loads((folder/'receipt.json').read_text())
        assert sha(raw)==receipt['body_sha256']
        if probe.get('parse_status')=='not_event_stream':continue
        fields=[];ordinal=0;count=0
        # Independent line-oriented parser. Unfinished final block is not emitted.
        for line in raw.splitlines(keepends=True):
            stripped=line.rstrip(b'\r\n')
            if not stripped and line.endswith(b'\n'):
                if fields:
                    e=json.loads(b'\n'.join(fields));count+=1
                    at=pd.Timestamp(e['at']);assert pd.Timestamp(receipt['params']['since'])<=at<=pd.Timestamp(receipt['params']['until'])
                    symbols={v for k,v in e['ca'].items() if k=='symbol' or k.endswith('_symbol')}
                    if symbols.intersection({'SPY','QQQ','VOO'}):mutations.append(dict(block_ordinal=ordinal,source_attempt=probe['attempt'],source_body_sha256=sha(raw),event=e,emitted_at_ns=at.value,original_announcement_time_verified=False,model_feature_admitted=False))
                fields=[];ordinal+=1
            elif stripped.startswith(b'data:'):fields.append(stripped[5:].removeprefix(b' '))
        assert count==probe['events'];all_events+=count
    assert tail==out['tail_occurrences'] and mutations==out['etf_mutations']
    assert len(tail)==report['tail_rows'] and len(mutations)==report['etf_mutations']
    result=dict(plan_sha256=plan['sha256'],inspection_sha256=sha((root/'INSPECTION.json').read_bytes()),tail_occurrences=len(tail),
        complete_stream_events=all_events,etf_mutations=len(mutations),all_raw_fields_and_links_exact=True,
        historical_availability_verified=False,complete_effective_date_history=False,model_feature_admitted=False)
    save(root/'INDEPENDENT_AUDIT.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    print(json.dumps(audit(p.parse_args().root),indent=2))
