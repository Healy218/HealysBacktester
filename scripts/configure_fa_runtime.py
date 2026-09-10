"""Render host-specific FA configuration and user systemd units; no activation."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    state=ROOT/'logs/job-health'
    mainroot=Path('/home/healy/Coding/HealysBacktester')
    cfg=dict(archive=str(ROOT/'fa/archive'),cohorts=str(ROOT/'fa/artifacts/prospective'),
             prices=str(ROOT/'fa/daily_prices'),liquid=str(ROOT/'v3/artifacts/universe_300.json'),
             baseline=str(ROOT/'v3/artifacts/universe_120.json'),aliases=str(ROOT/'fa/artifacts/aliases.json'),
             calendar=str(ROOT/'inputs/calendar.json'),state=str(state),server='mrhea@62.238.20.66',
             server_archive='/home/mrhea/HealysBacktester/fa/archive',gsutil='/home/healy/google-cloud-sdk/bin/gsutil',
             backup_roots=[[str(mainroot/'v3/data'),'gs://healys-backtester/backup/homebox/v3/data'],
                           [str(ROOT/'fa'),'gs://healys-backtester/backup/homebox/fa-runtime/fa'],
                           [str(ROOT/'inputs'),'gs://healys-backtester/backup/homebox/fa-runtime/inputs']],
             packed_backup={'source':str(mainroot/'nn_meta/data_cache_v5'),'destination':'gs://healys-backtester/backup/homebox/v5-packed'},
             job_hours={'archive-pull':3,'stocktwits-push':3,'fa-prices':48,'fa-tracker':48,'cache-backup':192,'fa-monthly':768},
             capture_hours={'news':48,'reddit':6,'stocktwits':3,'stocktwits_sentiment':3,'edgar':96},
             not_before={'fa-monthly':'2026-10-01T01:30:00+00:00'})
    for d in ['inputs','fa/artifacts/prospective','fa/daily_prices','logs/job-health','deploy/generated-user']:(ROOT/d).mkdir(parents=True,exist_ok=True)
    (ROOT/'deploy/fa-runtime.json').write_text(json.dumps(cfg,indent=2)+'\n')
    jobs=[('archive-pull','*-*-* *:15:00 UTC','archive',900),
          ('stocktwits-push','*-*-* *:25:00 UTC',None,1200),
          ('fa-prices','*-*-* 00:35:00 UTC','prices',1200),
          ('fa-monthly','*-*-01 01:15:00 UTC','monthly',3600),
          ('fa-tracker','*-*-* 01:00:00 UTC','tracker',1200),
          ('cache-backup','Sun *-*-* 03:00:00','backup',21600),
          ('fa-health','*-*-* *:45:00 UTC','health',600)]
    for name,schedule,job,timeout in jobs:
        command=f'{ROOT}/venv/bin/python {ROOT}/scripts/fa_runtime.py {job}' if job else f'/bin/bash {ROOT}/scripts/stocktwits_collect_push.sh'
        service=f'''[Unit]
Description=Healy FA {name}
[Service]
Type=oneshot
WorkingDirectory={ROOT}
Environment=OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
Nice=15
CPUQuota=50%
IOWeight=10
MemoryHigh=1G
MemoryMax=2G
TimeoutStartSec={timeout+30}
ExecStart={ROOT}/venv/bin/python {ROOT}/scripts/run_ops_job.py --name {name} --state-dir {state} --timeout {timeout} -- {command}
'''
        timer=f'''[Unit]
Description=Healy FA {name} schedule
[Timer]
OnCalendar={schedule}
Persistent=true
RandomizedDelaySec=60
Unit=healys-{name}.service
[Install]
WantedBy=timers.target
'''
        folder=ROOT/'deploy/generated-user'
        (folder/f'healys-{name}.service').write_text(service)
        (folder/f'healys-{name}.timer').write_text(timer)
    print('Rendered',len(jobs),'timers in',ROOT/'deploy/generated-user')

if __name__=='__main__':main()
