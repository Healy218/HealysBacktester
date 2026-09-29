"""Lossless factorization of frozen proposals into distinct execution horizons.

Only numerical replay inputs are shared. Original variant/feature rows remain in
their frozen stores, and multiplicities reconcile back to the complete census.
Targets remain distinct and are expanded by the execution consumer.
"""
from collections import Counter
import json
from pathlib import Path
import shutil
import sqlite3
import time

import pyarrow.parquet as pq

from nn_meta.v7.compact_proposals import SCHEMA
from nn_meta.v7.storage import identity, sha, verify, transaction, receipt

FIELDS = ['symbol', 'decision_ns', 'exit_decision_ns', 'censored_ns', 'is_put', 'exit_stock_ticker']


def compact_key(row):
    entry, exit_at, censored = row['decision_ns'], row['exit_decision_ns'], row['censored_ns']
    if type(entry) is not int or entry < 0 or (exit_at is None) == (censored is None):
        raise ValueError('Invalid execution horizon')
    end = exit_at if exit_at is not None else censored
    if type(end) is not int or end < entry or not isinstance(row['symbol'], str) or not row['symbol']:
        raise ValueError('Invalid execution clock or identity')
    if type(row['is_put']) is not bool:
        raise ValueError('Invalid execution direction')
    return (row['symbol'], entry, -1 if exit_at is None else exit_at,
            -1 if censored is None else censored, int(row['is_put']), row['exit_stock_ticker'] or '')


def proposal_from_key(key, security_id):
    symbol, decision, exit_at, censored, is_put, exit_symbol = key
    scope = dict(security_id=security_id, symbol=symbol, decision_ns=decision,
                 exit_decision_ns=None if exit_at == -1 else exit_at,
                 censored_ns=None if censored == -1 else censored,
                 right='P' if is_put else 'C', exit_stock_ticker=exit_symbol or None)
    return dict(scope, proposal_id=identity(dict(schema='v7-factorized-execution-path-v1', **scope)))


def add_batch(db, batch_id, digest, rows):
    """One atomic checkpoint owns both multiplicities and source completion."""
    existing = db.execute('SELECT digest,rows FROM batches WHERE path=?', (batch_id,)).fetchone()
    if existing:
        if existing[0] != digest:
            raise ValueError('Previously consumed proposal batch changed')
        return existing[1], False
    groups = Counter(compact_key(row) for row in rows)
    with db:
        db.executemany('INSERT INTO jobs VALUES(?,?,?,?,?,?,?) ON CONFLICT DO UPDATE SET multiplicity=multiplicity+excluded.multiplicity',
                       ((*key, count) for key,count in groups.items()))
        total = sum(groups.values())
        db.execute('INSERT INTO batches VALUES(?,?,?)', (batch_id,digest,total))
    return total, True


def connect_jobs(path):
    db = sqlite3.connect(path)
    db.executescript('''PRAGMA cache_size=-8192; PRAGMA temp_store=FILE; PRAGMA synchronous=FULL;
        CREATE TABLE IF NOT EXISTS jobs(symbol TEXT,decision_ns INTEGER,exit_ns INTEGER,censored_ns INTEGER,
        is_put INTEGER,exit_symbol TEXT,multiplicity INTEGER NOT NULL,
        PRIMARY KEY(symbol,decision_ns,exit_ns,censored_ns,is_put,exit_symbol)) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS batches(path TEXT PRIMARY KEY,digest TEXT,rows INTEGER) WITHOUT ROWID;''')
    return db


def guard(root, *, max_bytes, reserve_bytes):
    if shutil.disk_usage(root).free < reserve_bytes:
        raise ValueError('Execution working-store disk reserve reached')
    size = sum(p.stat().st_size for p in Path(root).rglob('*.sqlite3'))
    if size > max_bytes:
        raise ValueError('Execution working-store allocation reached')


def build_jobs(source, expected_digest, working, output, *, deadline=float('inf'),
               budget_root=None, max_bytes=20_000_000_000, reserve_bytes=20_000_000_000):
    source, working, output = map(Path, (source,working,output))
    if sha(source/'complete.json') != expected_digest:
        raise ValueError('Frozen entry-demand anchor changed')
    verify(source)
    demand = json.loads((source/'declaration.json').read_text())
    expected = json.loads((source/'report.json').read_text())['proposals']
    inputs = {str(source/'complete.json'):expected_digest, str(Path(__file__).resolve()):sha(__file__)}
    batches = []
    for store_text in demand['proposal_stores']:
        store = Path(store_text)
        for directory in [store/'declaration', store/'summary']:
            anchor = str(directory/'complete.json')
            if anchor not in demand['inputs'] or sha(anchor) != demand['inputs'][anchor]:
                raise ValueError('Proposal source anchor changed')
            verify(directory)
            inputs[anchor] = sha(anchor)
        declaration = json.loads((store/'declaration/declaration.json').read_text())
        if declaration['security_id'] != demand['security_id']:
            raise ValueError('Proposal security identity differs')
        summary = json.loads((store/'summary/report.json').read_text())
        for row in summary['batches']:
            batch = store/'batches'/str(row['batch'])
            inputs[str(batch/'complete.json')] = row['receipt_sha256']
            batches.append((batch,row['receipt_sha256'],row['proposals']))
    if sum(count for _,_,count in batches) != expected:
        raise ValueError('Frozen proposal/entry census differs')
    binding = dict(schema='v7-full-execution-jobs-v1', security_id=demand['security_id'],
                   demand=str(source), targets=demand['targets'], inputs=inputs,
                   key_fields=FIELDS, scope='All frozen proposals; shared execution horizons only')
    if output.exists():
        verify(output, expected_identity=identity(binding))
        return json.loads((output/'report.json').read_text())
    working.mkdir(parents=True,exist_ok=True)
    bound = working/'binding.json'
    if bound.exists() and json.loads(bound.read_text()) != binding:
        raise ValueError('Execution job checkpoint belongs to different inputs')
    if not bound.exists():
        bound.write_text(json.dumps(binding,sort_keys=True,indent=2)+'\n')
    db = connect_jobs(working/'jobs.sqlite3')
    try:
        for batch,digest,count in batches:
            if time.monotonic() >= deadline:
                return dict(status='checkpointed',security_id=demand['security_id'],
                            batches_complete=db.execute('SELECT COUNT(*) FROM batches').fetchone()[0])
            if sha(batch/'complete.json') != digest:
                raise ValueError('Frozen proposal batch anchor changed')
            if db.execute('SELECT 1 FROM batches WHERE path=?',(str(batch),)).fetchone():
                continue
            verify(batch)
            parquet = pq.ParquetFile(batch/'proposals.parquet')
            if not parquet.schema_arrow.equals(SCHEMA):
                raise ValueError('Compact proposal schema differs')
            # Original producer bounds each batch; additionally bound rows here.
            if parquet.metadata.num_rows > 2_000_000:
                raise ValueError('Unbounded source batch requires a smaller transaction plan')
            # Stream numerical columns; do not deserialize variant metadata per row.
            def rows():
                for chunk in parquet.iter_batches(batch_size=16384,columns=FIELDS):
                    yield from chunk.to_pylist()
            actual,_ = add_batch(db,str(batch),digest,rows())
            if actual != count:
                raise ValueError('Proposal batch row census differs')
            guard(budget_root or working,max_bytes=max_bytes,reserve_bytes=reserve_bytes)
        proposals = db.execute('SELECT COALESCE(SUM(multiplicity),0) FROM jobs').fetchone()[0]
        if proposals != expected:
            raise ValueError('Execution factorization lost or duplicated proposals')
        report = dict(status='planned',security_id=demand['security_id'],proposals=proposals,
                      distinct_horizons=db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],
                      proposal_target_rows=proposals*len(demand['targets']),
                      batches=db.execute('SELECT COUNT(*) FROM batches').fetchone()[0],
                      execution_complete=False,research_ready=False)
        if any(sha(p) != h for p,h in inputs.items()):
            raise ValueError('Execution job source changed')
        with transaction(output) as temp:
            with sqlite3.connect(temp/'jobs.sqlite3') as target:
                db.backup(target)
            for name,doc in [('binding.json',binding),('report.json',report)]:
                (temp/name).write_text(json.dumps(doc,sort_keys=True,indent=2)+'\n')
            receipt(temp,dict(identity=identity(binding),research_ready=False))
        return report
    finally:
        db.close()
