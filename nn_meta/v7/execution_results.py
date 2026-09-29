"""Factorized execution payloads with exact per-horizon reconstruction."""
from copy import deepcopy
import json
import zlib

from nn_meta.v7.storage import identity


def initialize(db):
    db.executescript('''PRAGMA cache_size=-8192; PRAGMA synchronous=FULL; PRAGMA temp_store=FILE;
        CREATE TABLE IF NOT EXISTS contents(content_id TEXT PRIMARY KEY,result BLOB) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS paths(path_id TEXT PRIMARY KEY,target INTEGER,multiplicity INTEGER,
            status TEXT,label_complete INTEGER,content_id TEXT,proposal_id TEXT,selection_id TEXT,horizon TEXT) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS pending(request_id TEXT PRIMARY KEY,request TEXT) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS links(path_id TEXT,request_id TEXT,PRIMARY KEY(path_id,request_id)) WITHOUT ROWID;''')


def store_result(db,result,proposal,target,multiplicity):
    """Caller commits a bounded batch; path, payload and request links are atomic."""
    path_id=result['path_id']
    content_id=result.get('shared_result_id',path_id)
    if not db.execute('SELECT 1 FROM contents WHERE content_id=?',(content_id,)).fetchone():
        payload={k:v for k,v in result.items() if k not in ('path_id','target_dte','security_id','source_horizon','source_multiplicity','shared_result_id')}
        db.execute('INSERT INTO contents VALUES(?,?)',(content_id,zlib.compress(json.dumps(payload,sort_keys=True,allow_nan=False).encode())))
    db.execute('INSERT INTO paths VALUES(?,?,?,?,?,?,?,?,?)',(path_id,target,multiplicity,result['status'],
        int(result['label_complete']),content_id,proposal['proposal_id'],result['selection_id'],json.dumps(proposal,sort_keys=True)))
    for request in result['pending']:
        encoded=json.dumps(request,sort_keys=True)
        old=db.execute('SELECT request FROM pending WHERE request_id=?',(request['request_id'],)).fetchone()
        if old and old[0]!=encoded:raise ValueError('Pending request identity collision')
        db.execute('INSERT OR IGNORE INTO pending VALUES(?,?)',(request['request_id'],encoded))
        db.execute('INSERT INTO links VALUES(?,?)',(path_id,request['request_id']))


def load_result(db,path_id):
    row=db.execute('SELECT p.target,p.multiplicity,p.proposal_id,p.selection_id,p.horizon,c.result '
                   'FROM paths p JOIN contents c USING(content_id) WHERE p.path_id=?',(path_id,)).fetchone()
    if row is None:raise KeyError(path_id)
    target,multiplicity,proposal_id,selection_id,horizon,payload=row
    proposal=json.loads(horizon);result=json.loads(zlib.decompress(payload))
    if 'proposal_id' in result:result['proposal_id']=proposal_id
    if 'replay' in result:result['replay']['proposal_id']=proposal_id
    result.update(selection_id=selection_id,path_id=path_id,target_dte=target,security_id=proposal['security_id'],
                  source_horizon=proposal,source_multiplicity=multiplicity)
    return result
