"""Prepare or run one explicitly selected post-freeze stage; preview by default."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STAGES = {'build': ['build', 'assemble'], 'evaluate': ['evaluate'], 'finalize': ['finalize']}


def require_receipt(path, label):
    if not path.exists() or json.loads(path.read_text()).get('returncode') != 0:
        raise ValueError(f'{label} must finish successfully first: {path}')


def prerequisites(root, campaign, stage):
    prep = root/'nn_meta/expanded_inputs'/campaign/'full-run'
    base = root/'nn_meta/campaigns'/campaign/'v6'
    freeze = prep/'worker-trial/result.json'
    if not freeze.exists():
        freeze = prep/'freeze-launcher-result.json'
    require_receipt(freeze, 'full freeze')
    if not json.loads(freeze.read_text()).get('freeze_completed') or not (base/'artifacts/baseline_spec.json').is_file():
        raise ValueError('verified merged freeze is not ready')
    if stage != 'build':
        require_receipt(base/'runs/next-stage/build-result.json', 'build and assembly')
        for name in ['meta_dataset.parquet','meta_dataset.marks.parquet']:
            if not (base/'artifacts'/name).is_file():
                raise ValueError(f'missing required dataset artifact: {name}')
    if stage == 'finalize':
        require_receipt(base/'runs/next-stage/evaluate-result.json', 'evaluation')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',required=True)
    parser.add_argument('--stage',required=True,choices=STAGES)
    parser.add_argument('--workers',type=int,choices=range(2,5),default=4)
    parser.add_argument('--run',action='store_true')
    args=parser.parse_args(argv)
    from scripts.research_local import name
    campaign=name(args.campaign)
    prep=ROOT/'nn_meta/expanded_inputs'/campaign
    resume=json.loads((prep/'resume.json').read_text())
    environment=resume['environment'].copy()
    final=prep/'full-run/final-inputs.json'
    digest=(prep/'full-run/final-inputs.sha256').read_text().strip()
    if hashlib.sha256(final.read_bytes()).hexdigest()!=digest:
        raise ValueError('sealed expanded input digest mismatch')
    environment.update(NN_META_POOL='v6',NN_META_CAMPAIGN=campaign,
                       NN_META_V6_INPUTS=str(final),NN_META_V6_INPUTS_SHA256=digest,
                       PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',OMP_NUM_THREADS='1',
                       OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMBA_NUM_THREADS='1',
                       TF_NUM_INTRAOP_THREADS='2',TF_NUM_INTEROP_THREADS='1')
    command=[str(ROOT/'venv/bin/python'),'-m','scripts.research_local','--campaign',campaign,'--pool','v6']
    for stage in STAGES[args.stage]:command+=['--stage',stage]
    command+=['--folds','3']
    if not args.run:
        print(json.dumps({'preview':True,'stages':STAGES[args.stage],
                          'command':command+['--workers',str(args.workers),'--run'],
                          'sealed_inputs':str(final),'sha256':digest,
                          'resource_policy':'At execution: up to 4 workers, 5 GiB/worker, 4 GiB available reserve, two physical cores excluded',
                          'evaluation':'Request 3 folds; original evaluator rejects folds overlapping frozen proposal optimization',
                          'requires':'Successful full freeze; build/assembly before evaluate; evaluate before finalize'},indent=2))
        return 0
    prerequisites(ROOT,campaign,args.stage)
    os.environ.update(environment)
    from scripts.run_v6_parallel_freeze import measure_resources,write_json
    resources=measure_resources(args.workers,per_worker_gib=5)
    cpus=sorted(cpu for group in resources['worker_cpu_groups'] for cpu in group)
    command=['taskset','--cpu-list',','.join(map(str,cpus))]+command+['--workers',str(resources['symbol_workers']),'--run']
    records=ROOT/'nn_meta/campaigns'/campaign/'v6/runs/next-stage'
    records.mkdir(parents=True,exist_ok=True)
    # A separate short admission lock prevents duplicate wrappers before the
    # original launcher's campaign lock is acquired after expensive preflight.
    from scripts.run_v6_parallel_freeze import lock
    with lock(records/'.next-stage.lock'):
        prerequisites(ROOT,campaign,args.stage)
        write_json(records/f'{args.stage}-plan.json',{'command':command,'resources':resources,'input_sha256':digest})
        with (records/f'{args.stage}.log').open('ab') as log:
            result=subprocess.run(command,cwd=ROOT,env=dict(os.environ,**environment),stdout=log,stderr=subprocess.STDOUT)
        write_json(records/f'{args.stage}-result.json',{'returncode':result.returncode,'stages':STAGES[args.stage]})
        return result.returncode


if __name__=='__main__':
    raise SystemExit(main())
