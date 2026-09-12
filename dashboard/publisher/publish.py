"""Publish one compact, replaceable dashboard document using server-only ADC.

Run from a dedicated checkout. Requires google-auth and requests. It never loads
provider keys or contacts trading APIs. --publish is an explicit mutation flag.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import time
from collect import collect_home, collect_server

def envelope(payload):
    raw=json.dumps(payload,allow_nan=False,separators=(',',':'))
    if len(raw.encode())>750_000:raise ValueError('Summary exceeds document budget')
    # Store JSON as a string: avoids index fanout on large nested arrays.
    return {'fields':{'schemaVersion':{'integerValue':'1'},'payload':{'stringValue':raw},'observedAt':{'timestampValue':payload['observedAt']}}}

def publish(project,payload):
    from google.auth import default
    from google.auth.transport.requests import AuthorizedSession
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]',project):raise ValueError('Invalid Firebase project ID')
    credentials,_=default(scopes=['https://www.googleapis.com/auth/datastore'])
    url=f'https://firestore.googleapis.com/v1/projects/{project}/databases/(default)/documents/dashboard/{payload["source"]}'
    with AuthorizedSession(credentials) as session:
        response=session.patch(url,json=envelope(payload),timeout=30,allow_redirects=False)
        if response.status_code!=200:raise RuntimeError(f'Firestore publish HTTP {response.status_code}')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',nargs='?',choices=['server','home'],default=os.environ.get('SOURCE'));p.add_argument('--root',type=Path,default=os.environ.get('SOURCE_ROOT'));p.add_argument('--progress',type=Path,default=os.environ.get('PROGRESS_RECEIPT'));p.add_argument('--project',default=os.environ.get('FIREBASE_PROJECT'));p.add_argument('--state',type=Path,default=os.environ.get('PUBLISHER_STATE'));p.add_argument('--publish',action='store_true')
    a=p.parse_args()
    if a.source not in ('server','home') or not all([a.root,a.project,a.state]):p.error('source, root, project and state are required (arguments or environment)')
    a.state.mkdir(parents=True,exist_ok=True)
    with (a.state/f'{a.source}.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        last=a.state/f'{a.source}.json'
        if last.exists() and time.time()-json.loads(last.read_text()).get('publishedEpoch',0)<55:raise RuntimeError('Publish rate limited: wait at least 55 seconds')
        payload=collect_server(a.root) if a.source=='server' else collect_home(a.root,a.progress,
            training_root=os.environ.get('TRAINING_ROOT'),training_campaign=os.environ.get('TRAINING_CAMPAIGN'))
        envelope(payload)
        if not a.publish:print(json.dumps({'mode':'dry-run','source':a.source,'issues':payload['issues']}));return
        publish(a.project,payload)
        record={'publishedEpoch':time.time(),'observedAt':payload['observedAt'],'source':a.source,'issues':payload['issues']}
        temp=last.with_suffix('.tmp');temp.write_text(json.dumps(record));temp.chmod(0o600);temp.replace(last)
        print(json.dumps(record))
if __name__=='__main__':main()
