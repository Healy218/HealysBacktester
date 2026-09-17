"""Install home paper calculations or the server operating watcher."""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import subprocess

from nn_meta.live.v6_market import save, utcnow
from nn_meta.live.v6_release import sha, verify_release

ROOT=Path(__file__).resolve().parents[1]


def quote(arguments):
    if any(any(c in str(a) for c in ('\n','\r','%','"','\\')) for a in arguments):
        raise ValueError('unsupported unit argument')
    return ' '.join('"'+str(a)+'"' for a in arguments)


def service(description,command,*,timeout=600,memory='18000M',extra=''):
    return f'''[Unit]
Description={description}
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory={ROOT}
Environment=OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1 TF_CPP_MIN_LOG_LEVEL=2 CUDA_VISIBLE_DEVICES=-1
Environment="MPLCONFIGDIR={ROOT}/nn_meta/live/v6_server/matplotlib"
ExecStart={quote(command)}
TimeoutStartSec={timeout}
MemoryMax={memory}
Nice=5
UMask=0077
{extra}
'''


def timer(description,unit,schedule):
    return f'''[Unit]
Description={description}

[Timer]
OnCalendar={schedule}
AccuracySec=1s
Persistent=true
Unit={unit}.service

[Install]
WantedBy=timers.target
'''


def install(args):
    release=ROOT/'deploy/v6/releases/v6-cash-repair-20260913'
    anchor=(release/'release.sha256').read_text().strip()
    verify_release(release,anchor)
    python=args.production/'venv/bin/python'
    state=ROOT/'nn_meta/live/v6_server'
    units={}
    if args.role=='home':
        activation=json.loads((state/'activation.json').read_text())
        if activation.get('status')!='passed' or activation.get('release_sha256')!=anchor:
            raise ValueError('paper runtime has not passed activation validation')
        for path,digest in activation['runtime_sha256'].items():
            if sha(ROOT/path)!=digest: raise ValueError('runtime changed after activation')
        common=[python,'-m','scripts.v6_forward_ops']
        units['healys-v6-forward.service']=service('Frozen V6 experimental paper expert',
            [python,'-m','scripts.run_v6_forward','--release',release,'--anchor',anchor,
             '--data-index',state/'data-index.json','--state',state,'--env',args.production/'.env',
             '--workers','16','--enable-alerts','--activation',state/'activation.json'],timeout=600,
             extra='ExecStartPost=-'+quote([python,'-m','scripts.v6_forward_ops','relay','--state',state,'--remote',args.remote]))
        units['healys-v6-forward.timer']=timer('V6 completed-bar paper decisions','healys-v6-forward',
            'Mon..Fri *-*-* 12..22:00,15,30,45:05 UTC')
        units['healys-v6-option-risk.service']=service('V6 option-midpoint loss and ITM expiry checks',
            [python,'-m','scripts.run_v6_option_risk','--state',state,'--env',args.production/'.env',
             '--activation',state/'activation.json','--enable-alerts'],timeout=55,memory='768M')
        units['healys-v6-option-risk.timer']=timer('Check V6 option risk each regular-market minute',
            'healys-v6-option-risk','Mon..Fri *-*-* 12..22:*:10 UTC')
        units['healys-v6-relay.service']=service('Publish V6 paper state and immutable alert events',
            [*common,'relay','--state',state,'--remote',args.remote],timeout=60,memory='512M')
        units['healys-v6-relay.timer']=timer('Retry V6 state and alert transfer each minute','healys-v6-relay','*-*-* *:*:40')
        units['healys-v6-data.service']=service('Refresh full-history V6 prior-session market context',
            [*common,'refresh','--state',state,'--env',args.production/'.env','--release',release,
             '--anchor',anchor,'--source',args.source,'--data-root',args.data_root],timeout=7200,memory='22000M')
        units['healys-v6-data.timer']=timer('Refresh V6 daily data before the next regular session',
            'healys-v6-data','Mon..Sat *-*-* 09,11,12:00:00 UTC')
    else:
        units['healys-v6-watch.service']=service('Monitor V6 paper production and server alert delivery',
            [python,'-m','scripts.v6_forward_ops','watch','--state',state,'--env',args.production/'.env',
             '--calendar',args.production/'nn_meta/live/exchange_calendar.json','--queue',args.production/'nn_meta/live/.alert_batches.sqlite3',
             '--notify'],timeout=45,memory='512M')
        units['healys-v6-watch.timer']=timer('Check V6 paper operation each minute','healys-v6-watch','*-*-* *:*:50')
    if not args.run:
        print(json.dumps(units,indent=2)); return
    receipt=state/'installations'/utcnow().strftime('%Y%m%dT%H%M%SZ')
    receipt.mkdir(parents=True)
    destination=Path.home()/'.config/systemd/user'
    destination.mkdir(parents=True,exist_ok=True)
    for name,content in units.items():
        target=destination/name
        if target.exists(): (receipt/(name+'.before')).write_bytes(target.read_bytes())
        (receipt/name).write_text(content)
    subprocess.run(['systemd-analyze','--user','verify',*[str(receipt/name) for name in units]],check=True)
    for name,content in units.items(): (destination/name).write_text(content)
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    if args.role=='server':
        subprocess.run(['systemctl','--user','disable','--now','healys-v6-observer.timer'],check=True)
    subprocess.run(['systemctl','--user','enable','--now',*[name for name in units if name.endswith('.timer')]],check=True)
    save(receipt/'receipt.json',{'role':args.role,'units':list(units),'release_sha256':anchor,
        'installed_at':utcnow().isoformat(),'paper_alerts':True,'broker_orders':False})
    print(json.dumps({'installed':True,'receipt':str(receipt)}))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--role',choices=['home','server'],required=True)
    ap.add_argument('--production',type=Path,required=True)
    ap.add_argument('--source',type=Path); ap.add_argument('--data-root',type=Path)
    ap.add_argument('--remote'); ap.add_argument('--run',action='store_true')
    install(ap.parse_args())
