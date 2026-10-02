"""Versioned wave persistence: transactional summaries and safe resume cursors.

Scientific tables remain byte-for-byte equivalent by value. Derived counters
and cursors commit with their cohorts; an uncommitted batch is wholly replayed.
"""
from contextlib import contextmanager
import fcntl,json,shutil,sqlite3
from pathlib import Path
from nn_meta.v7.storage import sha,identity,verify

class Writer:
    def __init__(self,db,batch=8):
        self.db,self.batch,self.pending=db,batch,0
        if batch<1:raise ValueError('Positive batch required')
        with db:
            exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='perf_counts'").fetchone()
            if not exists:
                db.executescript('''BEGIN IMMEDIATE;
                  CREATE TABLE perf_counts(name PRIMARY KEY,value INTEGER NOT NULL) WITHOUT ROWID;
                  CREATE TABLE perf_status(status PRIMARY KEY,members INTEGER,weight INTEGER) WITHOUT ROWID;
                  CREATE TABLE perf_exclusions(phase PRIMARY KEY,members INTEGER,weight INTEGER) WITHOUT ROWID;
                  CREATE TABLE perf_cursor(id INTEGER PRIMARY KEY CHECK(id=1),symbol,decision_ns,is_put);
                  INSERT INTO perf_status SELECT status,SUM(members),SUM(proposal_weight) FROM buckets GROUP BY status;
                  INSERT INTO perf_exclusions SELECT phase,SUM(members),SUM(proposal_weight) FROM exclusions GROUP BY phase;
                ''')
                for table in ['cohorts','buckets','contents','pending']:
                    db.execute('INSERT INTO perf_counts VALUES(?,?)',(table,db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]))
                    db.execute(f'''CREATE TRIGGER perf_count_{table} AFTER INSERT ON {table} BEGIN
                        UPDATE perf_counts SET value=value+1 WHERE name='{table}'; END''')
                db.execute('''CREATE TRIGGER perf_bucket AFTER INSERT ON buckets BEGIN
                    INSERT INTO perf_status VALUES(NEW.status,NEW.members,NEW.proposal_weight)
                    ON CONFLICT(status) DO UPDATE SET members=members+NEW.members,weight=weight+NEW.proposal_weight; END''')
                db.execute('''CREATE TRIGGER perf_exclusion AFTER INSERT ON exclusions BEGIN
                    INSERT INTO perf_exclusions VALUES(NEW.phase,NEW.members,NEW.proposal_weight)
                    ON CONFLICT(phase) DO UPDATE SET members=members+NEW.members,weight=weight+NEW.proposal_weight; END''')
    @contextmanager
    def cohort(self,key):
        try:
            # Explicit BEGIN ensures a new batch is transactional even before first write.
            if not self.db.in_transaction:self.db.execute('BEGIN IMMEDIATE')
            yield
            self.db.execute('INSERT OR REPLACE INTO perf_cursor VALUES(1,?,?,?)',key)
            self.pending+=1
            if self.pending>=self.batch:self.flush()
        except BaseException:
            self.db.rollback();self.pending=0;raise
    def flush(self):self.db.commit();self.pending=0
    def counts(self,table):return self.db.execute('SELECT value FROM perf_counts WHERE name=?',(table,)).fetchone()[0]
    def summary(self,table,column):
        if table not in ('perf_status','perf_exclusions') or column not in ('members','weight'):raise ValueError('Invalid summary')
        key='status' if table=='perf_status' else 'phase'
        return dict(self.db.execute(f'SELECT {key},{column} FROM {table} ORDER BY {key}'))
    def cohorts(self,source):
        from nn_meta.v7.execution_cohorts import cohorts
        cursor=self.db.execute('SELECT symbol,decision_ns,is_put FROM perf_cursor WHERE id=1').fetchone()
        where=' WHERE (symbol,decision_ns)>=(?,?)' if cursor else ''
        rows=source.execute('SELECT * FROM jobs'+where+' ORDER BY symbol,decision_ns,exit_ns,censored_ns,is_put,exit_symbol',cursor[:2] if cursor else ())
        for key,group in cohorts(rows):
            if cursor and key<=cursor:continue
            yield key,group

def selected_pending(source,entries,db):
    """Validate every plan key, but avoid fetching rows for already committed keys."""
    from scripts.plan_v7_pending_replay import selected_cohorts
    seen=set()
    for entry in entries:
        key=tuple(entry['key'])
        if key in seen or not entry['targets'] or len(set(entry['targets']))!=len(entry['targets']):raise ValueError('Duplicate cohort or target in replay plan')
        seen.add(key)
        if db.execute('SELECT 1 FROM cohorts WHERE symbol=? AND decision_ns=? AND is_put=?',key).fetchone():continue
        yield from selected_cohorts(source,[entry])

def inherit_checkpoint(parent,output,declaration,sid):
    """Copy a verified stopped predecessor, preserving its hashes as lineage.

    Never rewrite the predecessor binding to excuse a new source revision.
    """
    parent,output=Path(parent).resolve(),Path(output).resolve()
    receipt_path=output/'inherited-checkpoint.json'
    if receipt_path.exists():
        receipt=json.loads(receipt_path.read_text())
        if receipt['parent']!=str(parent):raise ValueError('Checkpoint parent changed')
        return receipt
    if (output/'securities').exists():raise ValueError('Unreceipted import; retain and inspect partial output')
    with (parent/'lock').open('r') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old=json.loads((parent/'declaration.json').read_text())
        if any(sha(p)!=h for p,h in old['inputs'].items()):raise ValueError('Parent source changed')
        if old['securities']!=[sid] or old['plan']!=declaration['plan'] or old['entry_root']!=declaration['entry_root']:raise ValueError('Parent scientific scope differs')
        # All frozen scientific inputs must be inherited, independent of producer files.
        for p,h in old['inputs'].items():
            if not p.endswith('.py') and declaration['inputs'].get(p)!=h:raise ValueError('Parent scientific input changed')
        if old.get('replay_plan')!=declaration.get('replay_plan'):raise ValueError('Parent replay scope differs')
        src=parent/'securities'/sid;binding=json.loads((src/'binding.json').read_text())
        if binding['campaign_identity']!=identity(old):raise ValueError('Parent wave binding differs')
        if binding['jobs_sha256']!=sha(Path(old['plan'])/'jobs'/sid/'complete.json'):raise ValueError('Parent jobs differ')
        verify(parent/'indexes'/sid)
        if binding['quote_index_sha256']!=sha(parent/'indexes'/sid/'complete.json'):raise ValueError('Parent quote index differs')
        output.mkdir(parents=True,exist_ok=True)
        shutil.copytree(parent/'indexes',output/'indexes')
        dst=output/'securities'/sid;dst.mkdir(parents=True)
        originals={}
        for name in ['wave.sqlite3','wave.sqlite3-journal','wave.sqlite3-wal','wave.sqlite3-shm']:
            if (src/name).exists():
                originals[name]=sha(src/name);shutil.copy2(src/name,dst/name)
                if sha(src/name)!=originals[name]:raise ValueError('Parent changed while copying')
        with sqlite3.connect(dst/'wave.sqlite3') as db:
            if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise ValueError('Inherited checkpoint corrupt')
        receipt=dict(parent=str(parent),parent_declaration_sha256=sha(parent/'declaration.json'),
            parent_identity=identity(old),parent_files=originals,recovered_database_sha256=sha(dst/'wave.sqlite3'))
        (dst/'parent-binding.json').write_text(json.dumps(binding,sort_keys=True)+'\n')
        receipt_path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
        return receipt
