"""Install the verified fresh Alpaca paper runtime and retire old V6 execution."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from scripts.run_v6_alpaca_runtime import ROOT,read,save,sha,clients
from integrations.alpaca_paper.v6_runtime import install_leg_capture

RUNTIME_FILES=['integrations/alpaca_paper/v6_bridge.py','integrations/alpaca_paper/v6_pricing.py',
               'integrations/alpaca_paper/v6_runtime.py','scripts/run_v6_alpaca_runtime.py',
               'scripts/run_v6_alpaca_scanner_v3.sh','scripts/lib/autosize.sh',
               'nn_meta/session_calendar.py','nn_meta/live/v6_option_sessions.py',
               'options/data/provider.py']
OLD_TIMERS=['healys-v6-forward.timer','healys-v6-option-risk.timer',
            'healys-v6-relay.timer','healys-v6-broker-ledger.timer','healys-v6-session-updates.timer']


def command(args):
    if any(any(c in str(a) for c in ('\n','\r','%','"','\\')) for a in args):
        raise ValueError('unsafe systemd argument')
    return ' '.join('"'+str(a)+'"' for a in args)


def units(state):
    common=[ROOT/'venv/bin/python','-m','scripts.run_v6_alpaca_runtime']
    result={}
    for name,cmd,memory,timeout,schedule in [
        ('scanner',['/usr/bin/bash',ROOT/'scripts/run_v6_alpaca_scanner_v3.sh','--state',state],
         '12G',600,'Mon..Fri *-*-* 09..16:00,15,30,45:05 America/New_York'),
        ('orders',[*common,'poll','--state',state], '1G',45,
         'Mon..Fri *-*-* 09..16:*:00,15,30,45 America/New_York')]:
        base='healys-v6-alpaca-'+name
        result[base+'.service']=f'''[Unit]
Description=V6 isolated Alpaca paper {name}
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory={ROOT}
Environment=OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMBA_NUM_THREADS=1 TF_CPP_MIN_LOG_LEVEL=2 CUDA_VISIBLE_DEVICES=-1
Environment=MPLCONFIGDIR={state}/matplotlib
ExecStart={command(cmd)}
TimeoutStartSec={timeout}
MemoryHigh={memory}
MemoryMax={memory}
MemorySwapMax=0
Nice=5
UMask=0077
NoNewPrivileges=true
'''
        result[base+'.timer']=f'''[Unit]
Description=V6 Alpaca paper {name} schedule

[Timer]
OnCalendar={schedule}
AccuracySec=1s
Persistent=false
Unit={base}.service

[Install]
WantedBy=timers.target
'''
    # Existing incubation reads the fresh scanner's candidates after cutover.
    source=(ROOT/'deploy/systemd/healys-ai-incubator-after-close.service').read_text()
    source=source.replace(str(state.parent/'v6_server'/'passes'),str(state/'passes'))
    source=source.replace(str(state.parent/'v6_server'/'data-index.json'),str(state/'data-index.json'))
    result['healys-ai-incubator-after-close.service']=source
    monitor=(ROOT/'deploy/systemd/healys-v6-alpaca-paper-monitor.service').read_text()
    monitor=monitor.replace('--output ', '--state '+str(state)+' --output ')
    result['healys-v6-alpaca-paper-monitor.service']=monitor
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--activate',action='store_true')
    a=p.parse_args();state=a.state.resolve();m=read(state/'paper-restart.json')
    planned=units(state)
    a.output.mkdir(parents=True,exist_ok=True)
    for name,body in planned.items(): (a.output/name).write_text(body)
    subprocess.run(['systemd-analyze','--user','verify',*[str(a.output/n) for n in planned]],check=True)
    if not a.activate:
        print(json.dumps({'status':'units_validated','units':list(planned)}));return
    if m.get('order_submission_enabled') or m.get('activated_at'):
        raise ValueError('existing activation requires review; never reset activation timestamp')
    trading,_=clients(ROOT/'.env');account=trading.get_account()
    import hashlib
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus
    if (hashlib.sha256(str(account.id).encode()).hexdigest()!=m['account_fingerprint'] or
            str(getattr(account.status,'value',account.status)).upper()!='ACTIVE' or
            account.trading_blocked or account.account_blocked or int(account.options_trading_level)<2 or
            trading.get_all_positions() or
            trading.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN,limit=500))):
        raise ValueError('activation requires the bound eligible empty paper account')
    frozen=Path(m['old_state']).parents[2]
    activation=read(state/'activation.json')
    for rel,digest in activation['runtime_sha256'].items():
        if sha(frozen/rel)!=digest: raise ValueError('frozen runtime changed: '+rel)
    database=state/'portfolio.sqlite3'
    if database.exists(): raise ValueError('activation requires fresh absent portfolio database')
    m.update(activated_at=datetime.now(timezone.utc).isoformat(),scanner_enabled=True,
             order_submission_enabled=False,bridge_runtime_sha256={r:sha(ROOT/r) for r in RUNTIME_FILES},
             activation_policy='prospective preview and reconciliation before each paper order',
             paper_only=True)
    # Construct ONLY schema/rules from the frozen portfolio implementation.
    # The historical database is never copied; no positions/events are imported.
    prepare='''import json,sqlite3,sys
from nn_meta.live.v6_portfolio import ForwardPortfolio
with sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True) as db:
    scope=json.loads(db.execute("SELECT value FROM metadata WHERE key='scope'").fetchone()[0])
ForwardPortfolio(sys.argv[2],scope=scope)
'''
    subprocess.run([sys.executable,'-c',prepare,str(Path(m['old_state'])/'portfolio.sqlite3'),str(database)],
                   cwd=frozen,check=True)
    database.chmod(0o600);install_leg_capture(database)
    save(state/'paper-restart.json',m)
    subprocess.run([sys.executable,'-m','scripts.run_v6_alpaca_runtime','check','--state',str(state)],
                   cwd=ROOT,check=True)
    unit_dir=Path.home()/'.config/systemd/user'
    backup=state/'retired-units';backup.mkdir(exist_ok=True)
    for name,body in planned.items():
        target=unit_dir/name
        if target.exists(): (backup/name).write_bytes(target.read_bytes())
        target.write_text(body)
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    # Retire the old account simulator/alerts, retain the daily input producer.
    subprocess.run(['systemctl','--user','disable','--now',*OLD_TIMERS],check=True)
    subprocess.run(['systemctl','--user','stop',*[n.replace('.timer','.service') for n in OLD_TIMERS]],check=True)
    m['order_submission_enabled']=True
    save(state/'paper-restart.json',m)
    subprocess.run(['systemctl','--user','enable','--now','healys-v6-alpaca-scanner.timer',
                    'healys-v6-alpaca-orders.timer'],check=True)
    subprocess.run(['systemctl','--user','start','healys-v6-alpaca-orders.service',
                    'healys-v6-alpaca-scanner.service'],check=True)
    save(state/'deployment.json',{'activated_at':m['activated_at'],'paper_only':True,
                                 'retired_timers':OLD_TIMERS,'units':list(planned),
                                 'data_producer':'healys-v6-data.timer'})
    print(json.dumps({'status':'paper_runtime_activated','state':str(state),'paper_only':True}))


if __name__=='__main__':main()
