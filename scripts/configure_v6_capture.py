"""Enable V6 evidence capture in the existing single shared feed processes.

Preview by default. Requires a git-deployed V6 checkout whose selftest passed.
No scanner thresholds, alert membership or notification settings are changed.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
MODULES=('nn_meta.live.feeds.option_stream','nn_meta.live.feeds.stock_stream')


def process_ids(module):
    found=[]
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args=path.read_bytes().rstrip(b'\0').split(b'\0')
            if (len(args)>=3 and args[-2:]==[b'-m',module.encode()]
                    and path.parent.stat().st_uid==os.getuid()
                    and (path.parent/'cwd').resolve()==ROOT):
                found.append(int(path.parent.name))
        except (FileNotFoundError,PermissionError,ProcessLookupError):
            continue
    return found


def updated_env(text, values):
    lines=text.splitlines()
    for key,value in values.items():
        if any(c in value for c in ('\n','\r','"','\\')):
            raise ValueError('invalid nonsecret environment value')
        matches=[i for i,line in enumerate(lines) if line.startswith(key+'=')]
        if len(matches)>1:
            raise ValueError(f'duplicate {key} environment entries')
        line=f'{key}="{value}"'
        if matches:
            lines[matches[0]]=line
        else:
            lines.append(line)
    return '\n'.join(lines)+'\n'


def configure(args):
    v6=args.v6_root.absolute()
    state=v6/'nn_meta/live/v6_server'
    test=json.loads((state/'selftest.json').read_text())
    spec=v6/'deploy/v6/releases/v6-cash-repair-20260913/baseline_spec.json'
    if test.get('status')!='passed' or test.get('members')!=40 or test.get('features')!=164:
        raise ValueError('V6 server selftest has not passed')
    symbols=json.loads(spec.read_text())['symbols']
    if not symbols:
        raise ValueError('empty V6 universe')
    values={'NN_META_OPTION_RECORD_TICKS':'1','NN_META_ADDITIONAL_STOCK_SPECS':str(spec)}
    env_path=ROOT/'.env'
    before=env_path.read_text()
    after=updated_env(before,values)
    plan={'tick_recording':True,'additional_stock_symbols':len(symbols),'v6_root':str(v6),
          'existing_processes':{m:process_ids(m) for m in MODULES},'alerts_enabled':False,
          'disk_reserve_gib':10,'max_tick_contracts_per_receipt_day':1000}
    if not args.run:
        print(json.dumps(plan,indent=2))
        return
    backup=ROOT/'nn_meta/live/feeds/data/v6-installations'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup.mkdir(parents=True,mode=0o700)
    copy=backup/'environment.before'
    copy.touch(mode=0o600)
    copy.write_text(before)
    tmp=env_path.with_suffix('.v6-tmp')
    tmp.touch(mode=0o600)
    tmp.write_text(after)
    tmp.replace(env_path)
    env=dict(os.environ,NN_META_POOL='v31')
    env.update(values)
    for module in MODULES:
        for pid in process_ids(module):
            os.kill(pid,signal.SIGTERM)
        deadline=time.monotonic()+15
        while process_ids(module) and time.monotonic()<deadline:
            time.sleep(.1)
        if process_ids(module):
            raise RuntimeError(f'{module} did not stop; no duplicate writer started')
        log=ROOT/'logs'/('feeds_options.log' if 'option_stream' in module else 'feeds_stock.log')
        with log.open('ab') as stream:
            subprocess.Popen([str(ROOT/'venv/bin/python'),'-m',module],cwd=ROOT,env=env,
                stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    (backup/'receipt.json').write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps({'configured':True,'receipt':str(backup/'receipt.json'),'alerts_enabled':False}))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--v6-root',type=Path,required=True)
    ap.add_argument('--run',action='store_true')
    configure(ap.parse_args())
