from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.measure_v7_wave_v1 import *
spec=json.loads((OUT/'benchmark.json').read_text());case=spec['cases']['small'];sid=case['security'];folder=OUT/'kill-resume';folder.mkdir(exist_ok=True)
for n in ['reference','interrupted']:shutil.copytree(OUT/'optimized/small',folder/n)
def count(path):
 with sqlite3.connect(path) as db:return db.execute("SELECT value FROM perf_counts WHERE name='cohorts'").fetchone()[0]
initial=count(folder/'reference/securities'/sid/'wave.sqlite3');target=initial+200
ref=command(spec['args'],'discover_v7_execution_wave_v3.py',folder/'reference',sid,case['seed'],200)
r=execute(ref,folder/'reference.log')
if r['exit_code']:raise ValueError('Reference failed')
cmd=command(spec['args'],'discover_v7_execution_wave_v3.py',folder/'interrupted',sid,case['seed'],200)
with (folder/'killed.log').open('w') as f:
 p=subprocess.Popen(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env=ENV)
 time.sleep(3)
 if p.poll() is not None:raise ValueError('Worker finished before kill test')
 p.kill();p.wait()
dbpath=folder/'interrupted/securities'/sid/'wave.sqlite3'
sidecars=[str(x) for x in dbpath.parent.glob('wave.sqlite3-*')]
# Preserve physical pre-recovery image before opening RW to recover hot journal.
recovery=folder/'pre-recovery';recovery.mkdir()
for p in [dbpath,*dbpath.parent.glob('wave.sqlite3-*')]:shutil.copy2(p,recovery/p.name)
committed=count(dbpath);remaining=target-committed
if remaining<=0:raise ValueError('Kill did not interrupt bounded workload')
cmd=command(spec['args'],'discover_v7_execution_wave_v3.py',folder/'interrupted',sid,case['seed'],remaining)
rr=execute(cmd,folder/'resumed.log')
values=[digest_database(folder/v/'securities'/sid/'wave.sqlite3') for v in ['reference','interrupted']]
save(folder/'verification.json',dict(initial=initial,target=target,committed_at_kill=committed,replayed_remaining=remaining,sidecars=sidecars,reference=r,resumed=rr,equal=values[0]==values[1],tables=values))
print('actual kill/resume parity',values[0]==values[1],initial,committed,target,flush=True)
if rr['exit_code'] or values[0]!=values[1]:raise ValueError('Actual kill/resume differs')
