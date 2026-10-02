import json,sqlite3,subprocess,sys
from pathlib import Path
import pytest
from nn_meta.v7.wave_performance_v1 import Writer,selected_pending

SCHEMA='''CREATE TABLE cohorts(symbol,decision_ns,is_put,horizons,proposals,PRIMARY KEY(symbol,decision_ns,is_put));
CREATE TABLE contents(content_id PRIMARY KEY,result);
CREATE TABLE buckets(bucket_id PRIMARY KEY,target,coverage,content_id,status,members,proposal_weight,label_complete);
CREATE TABLE pending(request_id PRIMARY KEY,request);
CREATE TABLE exclusions(bucket_id PRIMARY KEY,phase,members,proposal_weight);
CREATE TABLE links(bucket_id,request_id);'''
def database(path):
 db=sqlite3.connect(path);db.executescript(SCHEMA);return db

def insert(db,n):
 db.execute('INSERT INTO cohorts VALUES(?,?,?,?,?)',('SPY',n,0,2,4))
 db.execute('INSERT INTO buckets VALUES(?,?,?,?,?,?,?,?)',(str(n),1,'{}',str(n),'capture_incomplete',2,4,0))
 db.execute('INSERT OR IGNORE INTO pending VALUES(?,?)',('shared','{}'))
 db.execute('INSERT INTO contents VALUES(?,?)',(str(n),b'x'))
 db.execute('INSERT INTO exclusions VALUES(?,?,?,?)',(str(n),'entry',2,4))

def test_summary_bootstrap_and_atomic_increment(tmp_path):
 db=database(tmp_path/'wave.db')
 with db:insert(db,1)
 w=Writer(db,2)
 with w.cohort(('SPY',2,0)):insert(db,2)
 with w.cohort(('SPY',3,0)):insert(db,3)
 assert w.counts('cohorts')==3 and w.counts('pending')==1
 assert w.summary('perf_status','members')=={'capture_incomplete':6}
 assert w.summary('perf_exclusions','weight')=={'entry':12}
 with pytest.raises(RuntimeError):
  with w.cohort(('SPY',4,0)):
   insert(db,4);raise RuntimeError('interrupted')
 assert w.counts('cohorts')==3
 assert db.execute('SELECT decision_ns FROM perf_cursor').fetchone()==(3,)

def test_process_death_recovers_last_committed_batch(tmp_path):
 path=tmp_path/'wave.db';database(path).close()
 code='''import os,sqlite3
from tests.test_v7_wave_performance_v1 import insert
from nn_meta.v7.wave_performance_v1 import Writer
import sys
db=sqlite3.connect(sys.argv[1]);w=Writer(db,2)
for n in [1,2]:
 with w.cohort(('SPY',n,0)):insert(db,n)
with w.cohort(('SPY',3,0)):
 insert(db,3);os._exit(19)
'''
 p=subprocess.run([sys.executable,'-c',code,str(path)]);assert p.returncode==19
 db=sqlite3.connect(path);w=Writer(db,2)
 assert db.execute('pragma integrity_check').fetchall()==[('ok',)]
 assert w.counts('cohorts')==2 and w.summary('perf_status','members')=={'capture_incomplete':4}
 assert db.execute('SELECT decision_ns FROM perf_cursor').fetchone()==(2,)
 with w.cohort(('SPY',3,0)):insert(db,3)
 w.flush();assert w.counts('cohorts')==3

def source():
 db=sqlite3.connect(':memory:');db.execute('CREATE TABLE jobs(symbol,decision_ns,exit_ns,censored_ns,is_put,exit_symbol,multiplicity,PRIMARY KEY(symbol,decision_ns,exit_ns,censored_ns,is_put,exit_symbol)) WITHOUT ROWID')
 for n in [1,2,3]:
  for side in [0,1]:db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?)',('SPY',n,n+10,-1,side,'SPY',2))
 return db

def test_resume_keeps_other_side_and_inherited_gaps(tmp_path):
 db=database(tmp_path/'wave.db');s=source()
 with db:
  for n in [1,3]:db.execute('INSERT INTO cohorts VALUES(?,?,?,?,?)',('SPY',n,0,1,2))
 w=Writer(db,1)
 # No inferred max key from inherited, potentially gapped cohorts.
 assert len(list(w.cohorts(s)))==6
 with w.cohort(('SPY',1,1)):db.execute('INSERT INTO cohorts VALUES(?,?,?,?,?)',('SPY',1,1,1,2))
 assert [k for k,r in w.cohorts(s)]==[('SPY',2,0),('SPY',2,1),('SPY',3,0),('SPY',3,1)]


def test_replay_skips_source_reads_but_rejects_duplicate_plans(tmp_path):
 db=database(tmp_path/'wave.db');s=source()
 with db:db.execute('INSERT INTO cohorts VALUES(?,?,?,?,?)',('SPY',1,0,1,2))
 entries=[dict(key=['SPY',n,0],targets=[1],horizons=1,proposals=2) for n in [1,2]]
 statements=[];s.set_trace_callback(statements.append)
 assert [k for k,r in selected_pending(s,entries,db)]==[('SPY',2,0)]
 assert len(statements)==1
 with pytest.raises(ValueError,match='Duplicate'):list(selected_pending(s,[entries[0],entries[0]],db))
