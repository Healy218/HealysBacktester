"""Bounded local V7 performance harness; never advances selected campaign roots."""
from pathlib import Path
import argparse,cProfile,fcntl,hashlib,json,os,pstats,resource,shutil,sqlite3,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'nn_meta/validation/v7-performance-20261002-r0'
CASES={'small':'BBG000C3HSR0','large':'BBG000BB5006','large_database':'BBG000BCMBG4'}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
def prepare():
 campaign=ROOT/'nn_meta/validation/v7-execution-campaign-20260928-r1'
 spec=json.loads((campaign/'declaration.json').read_text());cases={}
 for name,sid in CASES.items():
  src=campaign/'waves'/sid;dst=OUT/'seeds'/name
  # Existing seeds are preserved if preparation was interrupted.
  with (src/'lock').open('r') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   if not dst.exists():shutil.copytree(src,dst)
  db=dst/'securities'/sid/'wave.sqlite3'
  with sqlite3.connect(db) as con:
   if con.execute('pragma quick_check').fetchone()!=('ok',):raise ValueError('Seed recovery failed')
  cases[name]=dict(security=sid,source=str(src),seed=str(dst),database_sha256=sha(db),
    progress=json.loads((src/'progress.json').read_text()))
 save(OUT/'benchmark.json',dict(cases=cases,campaign=str(campaign),max_cohorts=40,
     matching_requirement='Same inherited database and next 40 cohorts; timing includes startup and final input verification',
     args=dict({k:spec[k] for k in ['plan','base_index','entry_root']},
      **{k:str(ROOT/'nn_meta/validation'/v) for k,v in dict(references='v7-reference-reconciliation-20260928-full-r0',review='v7-reference-rename-review-20260928',hours='v7-dated-hours-20260927',blackouts='v7-contract-blackouts-20260928-approved').items()})))
 return cases

def run(name,variant='baseline',suffix='',profile=True,max_cohorts=40):
 spec=json.loads((OUT/'benchmark.json').read_text());case=spec['cases'][name];dst=OUT/(variant+suffix)/name
 if dst.exists():raise ValueError('Benchmark output exists')
 cmd=[str(ROOT/'venv/bin/python')]
 prof=OUT/(variant+suffix)/(name+'.prof');prof.parent.mkdir(parents=True,exist_ok=True)
 if profile:cmd+=['-m','cProfile','-o',str(prof)]
 cmd+=[str(ROOT/'scripts'/('discover_v7_execution_wave_v2.py' if variant=='baseline' else 'discover_v7_execution_wave_v3.py'))]
 if variant=='baseline':shutil.copytree(case['seed'],dst)
 else:cmd+=['--checkpoint-from',case['seed']]
 for k,v in spec['args'].items():cmd+=['--'+k.replace('_','-'),v]
 cmd+=['--security',case['security'],'--output',str(dst),'--max-seconds','300','--max-cohorts',str(max_cohorts)]
 began=time.monotonic()
 with (prof.with_suffix('.log')).open('w') as f:
  p=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMBA_NUM_THREADS='1'))
 elapsed=time.monotonic()-began
 result=dict(command=cmd,wall_seconds=elapsed,exit_code=p.returncode,profile=profile)
 if (dst/'progress.json').exists():result['progress']=json.loads((dst/'progress.json').read_text())
 if profile and prof.exists():
  stats=pstats.Stats(str(prof));rows=[]
  for (file,line,func),(cc,nc,tt,ct,callers) in stats.stats.items():rows.append(dict(file=file,line=line,function=func,calls=nc,self_seconds=tt,cumulative_seconds=ct))
  result['top_self']=sorted(rows,key=lambda r:r['self_seconds'],reverse=True)[:20]
  result['top_cumulative']=sorted(rows,key=lambda r:r['cumulative_seconds'],reverse=True)[:20]
 save(prof.with_suffix('.json'),result)
 print(json.dumps(dict(case=name,variant=variant,wall_seconds=elapsed,exit_code=p.returncode,receipt=str(prof.with_suffix('.json')))),flush=True)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--case',choices=CASES);p.add_argument('--variant',default='baseline');p.add_argument('--suffix',default='');p.add_argument('--no-profile',action='store_true');p.add_argument('--max-cohorts',type=int,default=40);a=p.parse_args()
 if a.action=='prepare':print(json.dumps(prepare(),default=str))
 else:run(a.case,a.variant,a.suffix,not a.no_profile,a.max_cohorts)
