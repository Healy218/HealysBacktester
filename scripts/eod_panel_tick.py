"""Calendar-aware minute cron: prewarm previews, deliver one EOD panel at C-5m.

Preview by default. --run enables worker launches and panel delivery. Normal
scanner state is not changed. Worker stdout is retained outside the alert logs.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import pandas as pd
from nn_meta import config
from nn_meta.session_calendar import configured_calendar, utc_naive
from nn_meta.live.state import state_lock, atomic_write_json


def phase(now, calendar):
    stamp=pd.Timestamp(now)
    day=stamp.tz_convert('America/New_York').strftime('%Y-%m-%d')
    bounds=calendar.bounds(day)
    if bounds is None:return day,'closed',None
    close=bounds[1];left=(close-utc_naive(now)).total_seconds()
    if 6*60 < left <= 14*60:return day,'prewarm',close
    if 4*60 < left <= 5*60:return day,'send',close
    return day,'idle',close


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',action='store_true');args=ap.parse_args()
    calendar=configured_calendar()
    if calendar is None:raise ValueError('captured exchange calendar required')
    day,action,close=phase(datetime.now(timezone.utc),calendar)
    print(json.dumps({'day':day,'action':action,'run':args.run}))
    if not args.run or action in ('closed','idle'):return
    root=config.ROOT/'live/eod_preview'/day;root.mkdir(parents=True,exist_ok=True)
    with state_lock(root/'.scheduler.lock'):
        if action=='prewarm':
            marker=root/'workers.json'
            if marker.exists():return
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
                     TF_NUM_INTRAOP_THREADS='1',TF_NUM_INTEROP_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
            capture=(close-pd.Timedelta(minutes=6)).tz_localize('UTC').isoformat()
            jobs=[]
            # Resource limits are operational preflight, not a claim of reserved memory.
            available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))
            if available < 4*1024*1024:
                atomic_write_json(marker,{'skipped':'less than 4 GiB available; recap will still send','jobs':[]});return
            for expert in ('v3','v31','v4','v5'):
                cmd=['nice','-n','10',sys.executable,'-m','nn_meta.live.eod_panel','--expert',expert,'--capture-at',capture]
                with (root/f'{expert}.log').open('ab') as log:
                    proc=subprocess.Popen(cmd,cwd=config.ROOT.parent,env=dict(env,NN_META_POOL='v31' if expert=='v4' else expert),
                        stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,start_new_session=True)
                jobs.append({'expert':expert,'pid':proc.pid,'command':cmd})
            atomic_write_json(marker,{'jobs':jobs,'capture_at':capture})
        else:
            result=subprocess.run([sys.executable,'-m','nn_meta.live.eod_panel','--send'],cwd=config.ROOT.parent)
            if result.returncode:raise SystemExit(result.returncode)

if __name__=='__main__':main()
