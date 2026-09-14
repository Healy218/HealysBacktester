"""Register the V6 immutable paper-event inbox with the existing dispatcher."""
import argparse
from pathlib import Path
import json
import os
import subprocess
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]


def install(args):
    from dotenv import dotenv_values, set_key
    env=ROOT/'.env'
    current=dotenv_values(env)
    cron=subprocess.check_output(['crontab','-l'],text=True)
    cron_enabled=any('nn_meta.live.alert_batches' in line and 'NN_META_ALERT_TOP_N=5' in line
                     and not line.lstrip().startswith('#') for line in cron.splitlines())
    if current.get('NN_META_ALERT_TOP_N')!='5' and not cron_enabled:
        raise ValueError('existing dispatcher is not enabled')
    spool=args.spool.absolute()
    spool.mkdir(parents=True,exist_ok=True)
    receipt=ROOT/'nn_meta/live/feeds/data/v6-installations'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    if not args.run:
        print(json.dumps({'spool':str(spool),'legacy_experts_unchanged':True})); return
    receipt.mkdir(parents=True)
    backup=receipt/'env.before'
    with backup.open('xb') as stream:
        os.chmod(backup,0o600); stream.write(env.read_bytes())
    set_key(str(env),'NN_META_V6_ALERT_SPOOL',str(spool))
    os.chmod(env,0o600)
    (receipt/'receipt.json').write_text(json.dumps({'spool':str(spool),'installed':True,
        'paper_only':True,'legacy_experts_unchanged':True})+'\n')
    print(json.dumps({'installed':True,'receipt':str(receipt/'receipt.json')}))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--spool',type=Path,required=True); ap.add_argument('--run',action='store_true')
    install(ap.parse_args())
