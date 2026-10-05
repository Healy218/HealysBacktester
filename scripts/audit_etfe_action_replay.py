"""Independent line-oriented audit of bounded action replay and timing witnesses."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from decimal import Decimal
import pandas as pd
from nn_meta.etfe.acquisition import sha,save,digest
from nn_meta.etfe.action_replay import verify,PARENT,TAIL


def audit(root):
    root=Path(root);plan=verify(root);report=json.loads((root/'RECONCILED.json').read_text())
    expected=[];unique={};duplicates=0;witness_events={};scope=[]
    for job in plan['jobs']:
        cursor=job['start'];done=False;count=0;day_ids=set();nbytes=0
        paths=sorted((root/'days'/job['day']).glob('page-*.json'));assert paths
        for page,path in enumerate(paths):
            assert not done and path.name==f'page-{page:06d}.json'
            pointer=json.loads(path.read_text());folder=root/pointer['attempt'];raw=(folder/'body').read_bytes();rec=json.loads((folder/'receipt.json').read_text())
            assert sha(raw)==rec['body_sha256'] and sha((folder/'receipt.json').read_bytes())==pointer['receipt_sha256']
            assert rec['params']==dict(since=cursor,until=job['end'],region='us',type=plan['type_filter'])
            assert rec['status']==200 and rec['error'] in (None,'byte_limit','response_time_limit')
            assert rec['plan_sha256']==plan['sha256'] and rec['headers']['content-type'].startswith('text/event-stream')
            nbytes+=len(raw);fields=[];block=0;events=[];prior=None
            for line in raw.splitlines(keepends=True):
                s=line.rstrip(b'\r\n')
                if not s and line.endswith(b'\n'):
                    if fields:
                        e=json.loads(b'\n'.join(fields));at=pd.Timestamp(e['at'])
                        assert pd.Timestamp(cursor)<=at<=pd.Timestamp(job['end']) and (prior is None or at>=prior)
                        prior=at;assert e['region']=='us' and e['event_type']==plan['type_filter'];events.append(e)
                        count+=1;day_ids.add(e['event_id']);h=digest(e)
                        if e['event_id'] in unique:assert unique[e['event_id']]==h;duplicates+=1
                        unique[e['event_id']]=h
                        if e['ca'].get('symbol') in ('SPY','QQQ','VOO'):
                            expected.append(dict(day=job['day'],page=page,block_ordinal=block,attempt=pointer['attempt'],body_sha256=sha(raw),event=e))
                            witness_events.setdefault(e['ca']['id'],{})[e['event_id']]=e
                    fields=[];block+=1
                elif s.startswith(b'data:'):fields.append(s[5:].removeprefix(b' '))
            done=rec['error'] is None
            if done:assert raw.endswith((b'\n\n',b'\r\n\r\n')) or not raw
            else:assert events;cursor=events[-1]['at']
        assert done
        scope.append(dict(day=job['day'],pages=len(paths),bytes=nbytes,event_occurrences=count,unique_events=len(day_ids),transport_eof=True,history_coverage_verified=False))
    f=root/report['files'][0]['path'];assert sha(f.read_bytes())==report['files'][0]['sha256']
    assert json.loads(f.read_text())['occurrences']==expected and report['days']==scope
    assert report['total_unique_events']==len(unique) and report['overlap_occurrences']==duplicates
    actions=[json.loads(x) for x in pd.read_parquet(PARENT/'ACTIONS.parquet').raw_json]
    actions += [r['raw'] for r in json.loads((TAIL/'OBSERVATIONS.json').read_text())['tail_occurrences']]
    assert len(report['action_witnesses'])==len(actions)
    matched=0
    for a,w in zip(actions,report['action_witnesses']):
        candidates=list(witness_events.get(a['id'],{}).values());before=[e for e in candidates if pd.Timestamp(e['at'])<pd.Timestamp(a['ex_date']+' 09:30',tz='America/New_York')]
        same=[e for e in before if e['action']!='delete' and e['ca'].get('symbol')==a['symbol'] and e['ca'].get('ex_date')==a['ex_date'] and Decimal(str(e['ca'].get('rate')))==Decimal(str(a['rate']))]
        assert w==dict(native_id=a['id'],symbol=a['symbol'],ex_date=a['ex_date'],mutations=len(candidates),pre_effective_mutations=len(before),matching_pre_effective_mutations=len(same),first_matching_emission=min((e['at'] for e in same),key=pd.Timestamp,default=None),original_publication_verified=False,latest_asof_version_verified=False,model_feature_admitted=False)
        matched+=bool(same)
    assert matched==report['actions_with_pre_effective_witness']
    result=dict(plan_sha256=plan['sha256'],reconciled_sha256=sha((root/'RECONCILED.json').read_bytes()),
        all_events_links_and_witnesses_exact=True,unique_events=len(unique),overlap_occurrences=duplicates,etf_occurrences=len(expected),
        actions_with_pre_effective_witness=matched,retention_verified=False,full_history_complete=False,model_feature_admitted=False)
    save(root/'INDEPENDENT_AUDIT.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    print(json.dumps(audit(p.parse_args().root),indent=2))
