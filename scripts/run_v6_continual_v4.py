#!/usr/bin/env python3
"""Bounded V6 data extension, fixed-family training and versioned research freeze."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime,timezone
import fcntl
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from incubator.continual.storage import sha,identity,write,seal,verify,publish_candidate


def configure(config):
    from scripts.run_v6_forward import configure as configure_frozen
    configure_frozen(Path(config['release']),config['release_sha256'])
    # A new namespace; never write into the parent campaign or paper state.
    os.environ['NN_META_CAMPAIGN']='v6-continual'
    source=json.loads(Path(config['data_index']).read_text())
    os.environ['NN_META_SESSION_CALENDAR']=str(Path(source['path'])/'calendar.json')
    from nn_meta import config as active
    expected=config.get('frozen_training_contract')
    if not expected:raise ValueError('missing frozen training configuration')
    actual=json.loads(json.dumps({k:getattr(active,k) for k in expected}))
    if actual!=expected:raise ValueError('V6 simulation/execution/training rules differ from frozen runtime')
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env')


def one_symbol(config,snapshot,symbol,root,through,run_dir,deadline):
    import logging
    from utils.logging_utils import setup_logging
    setup_logging(log_level=logging.ERROR)
    from incubator.daily_v6.data import build_symbol
    return build_symbol(config,snapshot,symbol,root,through,run_dir,deadline)


def runtime_sources():
    files=[*sorted((ROOT/'incubator/continual').glob('*.py')),*sorted((ROOT/'incubator/recovery_v6').glob('*.py')),*sorted((ROOT/'incubator/daily_v6').glob('*.py')),Path(__file__),
        ROOT/'v3/_source_memo.py',ROOT/'scripts/run_v6_continual_v4.sh',ROOT/'nn_meta/config.py',ROOT/'nn_meta/baseline.py',ROOT/'nn_meta/proposals.py',
        ROOT/'nn_meta/build_meta_dataset.py',ROOT/'nn_meta/live/v4_candidates.py',
        ROOT/'nn_meta/live/v6_forward_inputs.py',ROOT/'nn_meta/live/v6_market.py',
        ROOT/'nn_meta/v6_expansion.py',ROOT/'options/execution.py',ROOT/'nn_meta/decision_contracts.py',
        ROOT/'nn_meta/tradingview_features.py',ROOT/'nn_meta/price_basis.py',ROOT/'nn_meta/session_calendar.py',
        ROOT/'nn_meta/live/v4_scan.py',ROOT/'nn_meta/feature_contract.py',ROOT/'nn_meta/weekly_expiry.py',
        ROOT/'nn_meta/option_tick_dataset.py',ROOT/'scripts/lib/autosize.sh',ROOT/'scripts/run_v6_continual.sh',
        *sorted((ROOT/'signals').rglob('*.py')),*sorted((ROOT/'options').rglob('*.py')),
        *sorted((ROOT/'portfolio').rglob('*.py')),*sorted((ROOT/'strategies').rglob('*.py')),
        *sorted((ROOT/'indicators').rglob('*.py'))]
    return {str(p.relative_to(ROOT)):sha(p) for p in files}


def run(args):
    config=json.loads(args.config.read_text());configure(config)
    from incubator.schedule import last_closed_session
    from incubator.daily_v6.snapshot import select_snapshot
    from incubator.recovery_v6.training import assemble_delta,prepare_arrays,evaluate
    through=args.through or last_closed_session(Path(config['data_index']))
    if through>last_closed_session(Path(config['data_index'])):
        raise ValueError('cannot process an unfinished session')
    root=Path(config['root']);root.mkdir(parents=True,exist_ok=True)
    lock=(root/'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    started=time.monotonic();deadline=started+args.max_seconds
    from nn_meta.session_calendar import SessionCalendar
    from importlib.metadata import version
    index=json.loads(Path(config['data_index']).read_text())
    calendar=SessionCalendar(json.loads((Path(index['path'])/'calendar.json').read_text()))
    import pandas as pd
    now=pd.Timestamp.now(tz='UTC')
    upcoming=[opening.tz_localize('UTC') for opening,_ in calendar.sessions.values()
              if opening.tz_localize('UTC')>now]
    if not upcoming:raise ValueError('calendar lacks next trading session')
    morning_seconds=(min(upcoming)-pd.Timedelta(minutes=30)-now).total_seconds()
    if morning_seconds<=0:raise ValueError('morning cutoff reached; retain prior model')
    deadline=min(deadline,started+morning_seconds)
    sources=runtime_sources()
    contract={k:config[k] for k in ['release_sha256','base_dataset_sha256','append_start','validation_days','embargo_days']}
    contract['frozen_training_contract']=config['frozen_training_contract']
    contract['lineage']=config['lineage']
    contract['inherited_artifacts']=config['inherited_artifacts']
    contract['prefix_snapshot']=config['prefix_snapshot']
    contract['comparison_candidate']=config['comparison_candidate']
    contract['sources']=sources
    contract['runtime']={name:version(name) for name in ['numpy','pandas','pyarrow','vectorbt','lightgbm']}
    contract['runtime']['python']=sys.version
    config['contract_identity']=identity(contract)
    binding=root/'contract.json'
    if binding.exists() and json.loads(binding.read_text())!=contract:
        raise ValueError('continual source/configuration changed; select a new research root')
    if not binding.exists():write(binding,contract)
    run_dir=root/'runs'/through;run_dir.mkdir(parents=True,exist_ok=True)
    status=dict(schema='v6-continual-run-v1',through=through,started_at=datetime.now(timezone.utc).isoformat(),
                research_only=True,deployment_approved=False,training_started=False,
                contract_identity=config['contract_identity'],scope='pilot' if args.symbols else 'full_universe')
    def report(**values):
        stamp=datetime.now(timezone.utc).isoformat()
        if 'stage' in values and values['stage']!=status.get('stage'):
            status.setdefault('stage_events',[]).append(dict(stage=values['stage'],started_at=stamp,elapsed_seconds=time.monotonic()-started))
        status.update(values,updated_at=stamp,elapsed_seconds=time.monotonic()-started)
        write(run_dir/'status.json',status);write(root/'latest-run.json',status|{'run_dir':str(run_dir)})
    try:
        report(status='running',stage='snapshot')
        seed=config.get('bootstrap_snapshot')
        if seed and seed['through']==through:
            snapshot=Path(seed['path'])
            if sha(snapshot/'manifest.json')!=seed['sha256']:
                raise ValueError('bootstrap snapshot anchor changed')
            document=json.loads((snapshot/'manifest.json').read_text())
            if document['through']!=through or document['release_sha256']!=config['release_sha256']:
                raise ValueError('bootstrap snapshot scope changed')
        else:
            snapshot=select_snapshot(config,root,through)
        release=Path(config['release']);model=json.loads((release/'model/ensemble_config.json').read_text())
        universe=sorted(json.loads((release/'baseline_spec.json').read_text())['symbols'])
        symbols=args.symbols.split(',') if args.symbols else universe
        if not set(symbols)<=set(universe) or len(set(symbols))!=len(symbols):raise ValueError('invalid pilot universe')
        declaration=dict(through=through,snapshot=str(snapshot),snapshot_sha256=sha(snapshot/'manifest.json'),
                         symbols=symbols,contract_identity=config['contract_identity'])
        path=run_dir/'declaration.json'
        if path.exists() and json.loads(path.read_text())!=declaration:raise ValueError('run inputs changed; use new lineage')
        write(path,declaration)
        if (run_dir/'candidate/complete.json').exists():
            verify(run_dir/'candidate')
            verdict=json.loads((run_dir/'candidate/evaluation.json').read_text())
            publish_candidate(root,run_dir/'candidate',through,verdict['status'])
            report(status='candidate_already_frozen',stage='done')
            return status
        incumbent_path=run_dir/'incumbent.json'
        if not incumbent_path.exists():
            accepted=root/'latest-candidate.json'
            incumbent=(json.loads(accepted.read_text()) if accepted.exists() else
                       config['comparison_candidate'])
            write(incumbent_path,incumbent)
        incumbent=json.loads(incumbent_path.read_text())
        incumbent_root=Path(incumbent['path'])
        anchor=incumbent_root/('manifest.json' if incumbent.get('original') else 'complete.json')
        if sha(anchor)!=incumbent['sha256']:raise ValueError('incumbent anchor changed')
        if not incumbent.get('original'):verify(incumbent_root)
        from incubator.daily_v6.inheritance import ParentArtifacts
        ParentArtifacts(config).reuse_symbols(config,through,run_dir,symbols)
        completed={};todo=[]
        for symbol in symbols:
            location=run_dir/'symbols'/symbol
            if (location/'complete.json').exists():
                verify(location);completed[symbol]=json.loads((location/'inventory.json').read_text())['counts']
            else:todo.append(symbol)
        todo.sort(key=lambda s:(s not in config.get('repair_priority',[]),s))
        report(stage='candidates_and_labels',symbols_complete=len(completed),symbols_required=len(symbols))
        with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('spawn'),
                                 initializer=configure,initargs=(config,),max_tasks_per_child=1) as pool:
            futures={pool.submit(one_symbol,config,snapshot,s,root,through,run_dir,deadline):s for s in todo}
            errors=[]
            for future in as_completed(futures):
                symbol=futures[future]
                try:completed[symbol]=future.result()
                except Exception as exc:errors.append(dict(symbol=symbol,error=f'{type(exc).__name__}: {exc}'))
                report(symbols_complete=len(completed),errors=errors)
        if errors:raise ValueError(f'{len(errors)} symbol builds incomplete; preserved successful checkpoints')
        if runtime_sources()!=sources:raise ValueError('runtime changed while building')
        report(counts={k:sum(c[k] for c in completed.values()) for k in next(iter(completed.values()))})
        if args.symbols or args.build_only:
            report(status='pilot_complete' if args.symbols else 'build_complete',stage='done');return status
        delta=assemble_delta(run_dir,model['features'])
        if delta.empty:
            report(status='awaiting_matured_labels',stage='done');return status
        base=Path(config['base_dataset'])
        if sha(base)!=config['base_dataset_sha256']:raise ValueError('immutable base dataset changed')
        arrays=run_dir/'arrays'
        report(stage='prepare_training')
        prepare_arrays(base,run_dir/'delta.parquet',arrays,model['features'],config['validation_days'],
                       config['embargo_days'],config['append_start'])
        candidate=run_dir/'candidate';candidate.mkdir(exist_ok=True)
        plan_path=run_dir/'training-plan.json'
        if not plan_path.exists():write(plan_path,dict(threads=args.threads,members=model['run_ids']))
        training_plan=json.loads(plan_path.read_text())
        if training_plan['members']!=model['run_ids']:raise ValueError('training member plan changed')
        report(stage='training',training_started=True,members_required=len(model['run_ids']))
        for ordinal,member in enumerate(model['run_ids']):
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('nightly deadline reached; prior accepted model retained')
            subprocess.run([sys.executable,str(Path(__file__).resolve()),'--member',member,
                '--arrays',str(arrays),'--parent-model',str(release/'model'),'--candidate',str(candidate),
                '--threads',str(training_plan['threads'])],check=True,timeout=remaining,
                env={**os.environ,'OMP_NUM_THREADS':str(training_plan['threads']),'OPENBLAS_NUM_THREADS':'1'})
            report(members_complete=ordinal+1)
        report(stage='evaluation')
        verdict=evaluate(arrays,candidate,incumbent_root,model['run_ids'],deadline)
        if time.monotonic()>deadline:raise TimeoutError('evaluation missed deadline; prior model retained')
        if runtime_sources()!=sources:raise ValueError('runtime changed while training')
        # Old eligibility and validation metrics must never describe the new weights.
        new_model={k:model[k] for k in ['family','mode','threshold','dd_brake','label','features','run_ids','feature_contract_version']}
        new_model.update(eligible=False,research_only=True,parent_release_sha256=config['release_sha256'],incumbent=incumbent,
                         training_through=through,evaluation=verdict)
        write(candidate/'ensemble_config.json',new_model)
        write(candidate/'evaluation.json',verdict)
        files=['ensemble_config.json','evaluation.json']+[f'{m}/{f}' for m in model['run_ids'] for f in ['model.joblib','magnitude.joblib','complete.json']]
        receipt=seal(candidate,dict(parent_release_sha256=config['release_sha256'],arrays_sha256=sha(arrays/'complete.json'),
            incumbent=incumbent,dataset_delta_sha256=sha(run_dir/'delta.parquet'),contract=config['contract_identity']),files,
            research_only=True,deployment_approved=False)
        publish_candidate(root,candidate,through,verdict['status'])
        report(status='candidate_frozen',stage='done',verdict=verdict)
        return status
    except Exception as exc:
        report(status='blocked' if not isinstance(exc,TimeoutError) else 'deadline_reached',error=f'{type(exc).__name__}: {exc}')
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path);p.add_argument('--through');p.add_argument('--symbols')
    p.add_argument('--build-only',action='store_true');p.add_argument('--workers',type=int,default=1)
    p.add_argument('--threads',type=int,default=1);p.add_argument('--max-seconds',type=int,default=28800)
    p.add_argument('--member');p.add_argument('--arrays',type=Path);p.add_argument('--parent-model',type=Path);p.add_argument('--candidate',type=Path)
    a=p.parse_args()
    if a.member:
        from incubator.recovery_v6.training import train_member
        train_member(a.arrays,a.parent_model/a.member,a.candidate/a.member,a.threads);return
    if not a.config or min(a.workers,a.threads,a.max_seconds)<1:p.error('config and positive budgets required')
    print(json.dumps(run(a),sort_keys=True))

if __name__=='__main__':main()
