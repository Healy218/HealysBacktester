"""Bounded matched-checkpoint timing, exact parity and resource scaling."""
import argparse,concurrent.futures,fcntl,hashlib,json,os,shutil,sqlite3,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'nn_meta/validation/v7-performance-20261002-r0'
ENV=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='1')

def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
def execute(cmd,log):
 started=time.monotonic()
 with log.open('w') as f:
  p=subprocess.Popen(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env=ENV)
  _,status,u=os.wait4(p.pid,0);p.returncode=os.waitstatus_to_exitcode(status)
 return dict(exit_code=p.returncode,wall_seconds=time.monotonic()-started,max_rss_kib=u.ru_maxrss,
             input_blocks=u.ru_inblock,output_blocks=u.ru_oublock,cpu_seconds=u.ru_utime+u.ru_stime,command=cmd)
def command(args,script,dst,sid,seed=None,count=200):
 cmd=[str(ROOT/'venv/bin/python'),str(ROOT/'scripts'/script)]
 for k,v in args.items():cmd+=['--'+k.replace('_','-'),v]
 cmd+=['--security',sid,'--output',str(dst),'--max-seconds','300','--max-cohorts',str(count)]
 if seed:cmd+=['--checkpoint-from',str(seed)]
 return cmd

def digest_database(path):
 with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as db:
  result={}
  for table in ['cohorts','contents','buckets','exclusions','pending','links']:
   h=hashlib.sha256();n=0
   cols=[r[1] for r in db.execute('PRAGMA table_info('+table+')')]
   for row in db.execute('SELECT * FROM '+table+' ORDER BY '+','.join(cols)):
    h.update(json.dumps([{'bytes':v.hex()} if isinstance(v,bytes) else v for v in row],separators=(',',':'),ensure_ascii=True).encode());n+=1
   result[table]=dict(count=n,sha256=h.hexdigest())
  return result

def compare():
 spec=json.loads((OUT/'benchmark.json').read_text())
 for round_name,variants in [('resume',['baseline','optimized']),('round2',['optimized','baseline'])]:
  for name,case in spec['cases'].items():
   for variant in variants:
    target=OUT/variant/(name+'.'+round_name+'.json')
    if target.exists():raise ValueError('Comparison receipt already exists')
    dst=OUT/variant/name;before=json.loads((dst/'progress.json').read_text())
    cmd=command(spec['args'],'discover_v7_execution_wave_v2.py' if variant=='baseline' else 'discover_v7_execution_wave_v3.py',dst,case['security'],case['seed'] if variant=='optimized' else None)
    d=execute(cmd,target.with_suffix('.log'))
    after=json.loads((dst/'progress.json').read_text())
    d.update(case=name,variant=variant,cohorts=after['cohorts_discovered']-before['cohorts_discovered'],assessments=after['distinct_horizon_targets_covered']-before['distinct_horizon_targets_covered'])
    save(target,d)
    if d['exit_code']:raise ValueError('Comparison failed')
    print(name,variant,round_name,d['wall_seconds'],flush=True)

def parity():
 spec=json.loads((OUT/'benchmark.json').read_text());report={}
 for name,case in spec['cases'].items():
  values=[digest_database(OUT/v/name/'securities'/case['security']/'wave.sqlite3') for v in ['baseline','optimized']]
  report[name]=dict(equal=values[0]==values[1],tables=values)
  print(name,report[name]['equal'],flush=True)
 save(OUT/'parity-resumed.json',report)
 if not all(x['equal'] for x in report.values()):raise ValueError('Scientific result mismatch')

def replay():
 src=ROOT/'nn_meta/validation/v7-required-inputs-20260930-r0/epochs/00001/replay';sid='BBG000BB5006'
 args=json.loads((src/'declaration.json').read_text())['arguments'];folder=OUT/'replay';seed=folder/'seed'
 folder.mkdir(exist_ok=True)
 with (src/'waves'/sid/'lock').open('r') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  shutil.copytree(src/'waves'/sid,seed)
 for variant in ['baseline','optimized']:
  dst=folder/variant
  if variant=='baseline':shutil.copytree(seed,dst)
  cmd=command(args,'replay_v7_pending_wave.py' if variant=='baseline' else 'replay_v7_pending_wave_v2.py',dst,sid,seed if variant=='optimized' else None,count=40)
  d=execute(cmd,folder/(variant+'.log'));save(folder/(variant+'.json'),d);print(variant,d['wall_seconds'],d['exit_code'],flush=True)
  if d['exit_code']:raise ValueError('Replay benchmark failed')
 values=[digest_database(folder/v/'securities'/sid/'wave.sqlite3') for v in ['baseline','optimized']]
 save(folder/'parity.json',dict(equal=values[0]==values[1],tables=values))
 if values[0]!=values[1]:raise ValueError('Replay mismatch')
 # Same next cohort set, optimized first to reverse cache-order advantage.
 for variant in ['optimized','baseline']:
  cmd=command(args,'replay_v7_pending_wave.py' if variant=='baseline' else 'replay_v7_pending_wave_v2.py',folder/variant,sid,seed if variant=='optimized' else None,count=200)
  d=execute(cmd,folder/(variant+'.resume.log'));save(folder/(variant+'.resume.json'),d);print('replay resumed',variant,d['wall_seconds'],d['exit_code'],flush=True)
 values=[digest_database(folder/v/'securities'/sid/'wave.sqlite3') for v in ['baseline','optimized']]
 save(folder/'parity-resumed.json',dict(equal=values[0]==values[1],tables=values))
 if values[0]!=values[1]:raise ValueError('Resumed replay mismatch')

def scaling(balanced=False):
 spec=json.loads((OUT/'benchmark.json').read_text())
 # Twice observed ~0.5GiB working sets plus buffer; preserve 18GiB for V6/host.
 sizing=subprocess.check_output(['bash','-c','source scripts/lib/autosize.sh; autosize_workers 1536 18432'],cwd=ROOT,text=True)
 ceiling=min(4,int(sizing));counts=[n for n in [1,2,4] if n<=ceiling]
 tasks=['small','large','large_database','small']*(2 if balanced else 1)
 folder=OUT/('scaling-balanced' if balanced else 'scaling');folder.mkdir(exist_ok=True)
 memory=Path('/proc/meminfo').read_text();prepared={}
 # Prepare all independent copies outside timed execution.
 for workers in counts:
  prepared[workers]=[]
  for i,name in enumerate(tasks):
   dst=folder/str(workers)/(str(i)+'-'+name);dst.parent.mkdir(exist_ok=True)
   shutil.copytree(OUT/'optimized'/name,dst)
   c=spec['cases'][name]
   cmd=command(spec['args'],'discover_v7_execution_wave_v3.py',dst,c['security'],c['seed'],count=200)
   prepared[workers].append((cmd,dst.with_suffix('.log'),dst,c))
 report=dict(autosize_ceiling=ceiling,per_worker_mb=1536,reserve_mb=18432,memory_before=memory,cohorts_per_task=200,task_mix=tasks,runs={})
 for workers in counts:
  start=time.monotonic()
  with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
   futures=[pool.submit(execute,cmd,log) for cmd,log,dst,c in prepared[workers]]
   results=[f.result() for f in futures]
  report['runs'][workers]=dict(wall_seconds=time.monotonic()-start,tasks=results)
  if any(r['exit_code'] for r in results):raise ValueError('Scaling worker failed')
  save(folder/'timings.json',report);print('scaling',workers,report['runs'][workers]['wall_seconds'],flush=True)
 # Same key/result digest of newly added cohorts is established by full DB comparison.
 fingerprints={}
 for workers in counts:
  fingerprints[workers]=[digest_database(dst/'securities'/c['security']/'wave.sqlite3') for cmd,log,dst,c in prepared[workers]]
 save(folder/'parity.json',dict(equal=all(x==fingerprints[counts[0]] for x in fingerprints.values()),tables=fingerprints))
 if not all(x==fingerprints[counts[0]] for x in fingerprints.values()):raise ValueError('Scaling output mismatch')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['compare','parity','replay','scaling','balanced']);a=p.parse_args();scaling(balanced=True) if a.action=='balanced' else globals()[a.action]()
