"""Install the explicitly authorized ten-minute paper window; no direct orders.

--apply drains consumers under existing locks and preserves prior manifests.
"""
from pathlib import Path
import contextlib,fcntl,json,subprocess,time
from datetime import datetime,timezone
from scripts.run_v6_alpaca_runtime_v6 import ROOT,save,sha,validate
STATE=Path('/home/healy/Coding/HealysV6/nn_meta/live/v6_alpaca_paper')
OUT=ROOT/'nn_meta/validation/v6-ten-minute-20261002-r0'
UNIT=Path.home()/'.config/systemd/user'
ADDED=['integrations/alpaca_paper/'+n+'.py' for n in [
 'v6_entry_window_v1','v6_bridge_v5','v6_step_slices_v3','v6_source_reconcile_v4']]+[
 'scripts/'+n for n in ['run_v6_alpaca_runtime_v6.py','run_v6_alpaca_scanner_v11.py',
 'run_v6_alpaca_scanner_v11.sh','run_v6_forward_resilient_v2.py','v6_portfolio_ten_minute_v1.py']]
DROPS=['healys-v6-alpaca-scanner.service.d/99-ten-minute-v11.conf',
       'healys-v6-alpaca-orders.service.d/99-ten-minute-v6.conf']
TIMERS=['healys-v6-alpaca-scanner.timer','healys-v6-alpaca-orders.timer']
def run(*cmd):return subprocess.run(cmd,check=True,capture_output=True,text=True).stdout
def verify_old(m):
 if not m.get('paper_only') or m.get('entry_window_policy'):raise ValueError('Expected predecessor paper manifest')
 frozen=Path(m['old_state']).parents[2]
 for root,hashes in [(ROOT,m['bridge_runtime_sha256']),(frozen,json.loads((STATE/'activation.json').read_text())['runtime_sha256'])]:
  for rel,h in hashes.items():
   if sha(root/rel)!=h:raise ValueError('Existing source changed: '+rel)
def main(apply=False):
 OUT.mkdir(parents=True,exist_ok=True)
 m=json.loads((STATE/'paper-restart.json').read_text());verify_old(m)
 parent=sha(STATE/'paper-restart.json');added={r:sha(ROOT/r) for r in ADDED}
 proposed=dict(m,entry_window_policy='signal-close-ten-minute-v1',entry_window_seconds=600,
   scanner_book_policy='archive-expired-never-filled-source-v4-ten-minute',
   scanner_monitor_policy='concurrent-quote-retry-ten-minute-v2',
   bridge_runtime_sha256=dict(m['bridge_runtime_sha256'],**added),
   entry_window_revision_at=datetime.now(timezone.utc).isoformat(),entry_window_parent_sha256=parent)
 save(OUT/'proposed-manifest.json',proposed)
 print(json.dumps(dict(status='prepared',entry_window_seconds=600,parent=parent,added_sources=added)),flush=True)
 if not apply:return
 backup=STATE/'runtime-revisions/ten-minute-v1-20261002'
 if backup.exists() or any((UNIT/p).exists() for p in DROPS):raise ValueError('Revision exists; inspect before retry')
 active={n:subprocess.run(['systemctl','--user','is-active','--quiet',n]).returncode==0 for n in TIMERS}
 if not all(active.values()):raise ValueError('Expected paper timers active')
 changed=False;committed=False
 try:
  run('systemctl','--user','stop',TIMERS[0])
  with contextlib.ExitStack() as stack:
   for name in ['scanner-dispatch.lock','bridge.lock','.forward.lock']:
    if name=='bridge.lock':run('systemctl','--user','stop',TIMERS[1])
    stream=stack.enter_context((STATE/name).open('a+'));deadline=time.monotonic()+660
    while True:
     try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB);break
     except BlockingIOError:
      if time.monotonic()>deadline:raise TimeoutError(name+' did not drain')
      time.sleep(1)
   if sha(STATE/'paper-restart.json')!=parent:raise ValueError('Manifest changed during drain')
   verify_old(m);backup.mkdir()
   (backup/'paper-restart.json').write_bytes((STATE/'paper-restart.json').read_bytes())
   for n in ['healys-v6-alpaca-scanner.service','healys-v6-alpaca-orders.service']:
    (backup/(n+'.txt')).write_text(run('systemctl','--user','cat',n))
   changed=True;save(STATE/'paper-restart.json',proposed)
   for p in DROPS:
    target=UNIT/p;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes((ROOT/'deploy/systemd'/p).read_bytes())
   run('systemctl','--user','daemon-reload');validate(STATE,require_fresh=True)
   save(OUT/'deployment.json',dict(observed_at=datetime.now(timezone.utc).isoformat(),
    parent_manifest_sha256=parent,manifest_sha256=sha(STATE/'paper-restart.json'),
    entry_window_seconds=600,backup=str(backup),added_sources=added,
    quote_freshness_seconds=30,order_ladder_seconds=300,model_changed=False,
    installer_sha256=sha(Path(__file__)),units={n:run('systemctl','--user','cat',n) for n in [
     'healys-v6-alpaca-scanner.service','healys-v6-alpaca-orders.service']}))
   committed=True
 finally:
  if changed and not committed:
   (STATE/'paper-restart.json').write_bytes((backup/'paper-restart.json').read_bytes())
   for p in DROPS:(UNIT/p).unlink(missing_ok=True)
   run('systemctl','--user','daemon-reload')
  run('systemctl','--user','start',*[n for n in TIMERS if active[n]])
 print('Ten-minute paper runtime deployed; scheduled timers restored.',flush=True)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
