"""Admit the largest budgeted discovery pool, accounting for workers already resident."""
from datetime import datetime
from pathlib import Path
import os
import math
import subprocess
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
MIB=1024**2
WORKER_MIB=1024
SERVICE_WORKER_MIB=12*1024  # Leave 2 GiB of the 14-GiB hard cap for controller/cache.
CGROOT=Path('/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service/app.slice')


def anon_mib(unit):
    path=CGROOT/unit/'memory.stat'
    if not path.exists():return 0
    stats=dict(line.split() for line in path.read_text().splitlines())
    return (int(stats.get('anon',0))+int(stats.get('kernel',0)))//MIB


def admission(maximum, *, now=None, available_mib=None, own_mib=None,
              paper_mib=None, incubator_mib=None, replay_mib=None, cpus=None, autosized=None, active_workers=0):
    local=(now or datetime.now().astimezone()).astimezone(ZoneInfo('America/Chicago'))
    if available_mib is None:
        fields=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
        available_mib=int(fields['MemAvailable'].split()[0])//1024
    if own_mib is None:own_mib=anon_mib('healys-v7-required-discovery-20260930.service')
    if paper_mib is None:paper_mib=anon_mib('healys-v6-alpaca-scanner.service')
    if incubator_mib is None:incubator_mib=anon_mib('healys-v6-continual.service')
    if replay_mib is None:replay_mib=anon_mib('healys-v7-required-frontier-20260930.service')
    if cpus is None:cpus=os.cpu_count() or 1
    minute=local.hour*60+local.minute
    paper_window=local.weekday()<5 and 7*60<=minute<15*60+30
    daily_window=local.weekday()<5 and 15*60+30<=minute<21*60
    paper_target=12288 if paper_window or paper_mib>64 else 0
    incubator_target=20480 if daily_window or incubator_mib>512 else 0
    reserve=4096+max(0,paper_target-paper_mib)+max(0,incubator_target-incubator_mib)+max(0,1024-replay_mib)
    # MemAvailable already subtracts our anonymous memory. Add it once so the
    # result is total pool capacity, not additional capacity mistaken for total.
    pool=max(0,available_mib+own_mib-reserve)
    worker_mib=max(WORKER_MIB,math.ceil(own_mib*1.5/max(1,active_workers)/256)*256) if active_workers else WORKER_MIB
    capacity=pool//worker_mib
    # Keep shared autosizing's CPU/admission convention while expressing the
    # ownership adjustment as a reduced reserve. No floor-one admission leak.
    if autosized is None:
        autosized=int(subprocess.check_output(['bash','-c',
            'source scripts/lib/autosize.sh; autosize_workers "$1" "$2"',
            'v7-discovery-resources-v3',str(worker_mib),str(reserve-own_mib)],cwd=ROOT,text=True).strip())
    ceiling=min(maximum,max(1,cpus-2),SERVICE_WORKER_MIB//worker_mib)
    limit=max(0,min(ceiling,capacity,autosized))
    return dict(admitted_workers=limit,worker_ceiling=ceiling,per_worker_mib=worker_mib,
        available_mib=available_mib,owned_anon_kernel_mib=own_mib,reserve_mib=reserve,
        paper_mib=paper_mib,incubator_mib=incubator_mib,replay_mib=replay_mib,
        paper_reservation=paper_window,daily_reservation=daily_window,
        cpu_threads=cpus,policy='v7-discovery-resources-v3')
