"""Separate numerical worker threads from autosizer CPU discovery."""
import os
from pathlib import Path
import subprocess
from scripts.v7_discovery_resources_v3 import admission as budget_admission

ROOT=Path(__file__).resolve().parents[1]


def admission(maximum, **kwargs):
    explicit=kwargs.pop('autosized',None)
    decision=budget_admission(maximum,autosized=explicit if explicit is not None else 1_000_000,**kwargs)
    if explicit is None:
        environment={k:v for k,v in os.environ.items() if k not in ['OMP_NUM_THREADS','OMP_THREAD_LIMIT']}
        count=int(subprocess.check_output(['bash','-c',
            'source scripts/lib/autosize.sh; autosize_workers "$1" "$2"',
            'v7-discovery-resources-v4',str(decision['per_worker_mib']),
            str(decision['reserve_mib']-decision['owned_anon_kernel_mib'])],
            cwd=ROOT,env=environment,text=True).strip())
        decision['admitted_workers']=min(decision['admitted_workers'],count)
        decision['autosized_workers']=count
    decision['policy']='v7-discovery-resources-v4'
    return decision
