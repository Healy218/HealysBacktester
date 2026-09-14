"""Explicit derived-artifact continuation after a completed symbol build.

Preserves the parent scope and shards, seals copies under a NEW campaign,
and checks the source, runtime and consumed inputs between stages. Raw option
archives are not reread: the parent build's provenance remains the evidence
for those bytes. Preview by default. No deployment or notifications.
"""
from __future__ import annotations
import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from scripts.research_local import name, campaign_lock, RUNTIME_PACKAGES

ROOT = Path(__file__).resolve().parents[1]
PERFORMANCE_CHANGES = {'nn_meta/build_meta_dataset.py', 'nn_meta/v4_evaluate.py',
    'nn_meta/v4_finalize.py', 'nn_meta/v4_loader.py', 'nn_meta/mark_stream.py',
    'nn_meta/temporal_validation.py'}
NEW_SOURCES = {'nn_meta/stream_assembly.py', 'nn_meta/training_jobs.py',
    'nn_meta/training_experiments.py', 'scripts/continue_v6_training.py',
    'nn_meta/neural_validation.py'}
# Reviewed inference/validation changes; no regenerated labels or proposals.
NEURAL_REPAIR_CHANGES = {'nn_meta/v4_accounting.py', 'nn_meta/v6_expansion.py',
                         'nn_meta/live/v4_scan.py'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path = Path(path); tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, sort_keys=True, indent=2)+'\n'); tmp.replace(path)


def read_parent_scope(path):
    """Read the launcher's pretty JSON without materializing millions of rows.

    Recognizes that writer's exact indentation, fails on unexpected shape,
    parses retained records with json, and hashes every byte of the original.
    """
    h = hashlib.sha256(); header=[]; suffix=[]; retained=[]; record=[]
    inside=False; finished=False; count=0
    with Path(path).open('rb') as f:
        for line in f:
            h.update(line)
            if not inside and not finished:
                header.append(line)
                if line == b'    "files": [\n': inside=True
            elif inside:
                if line == b'    ],\n':
                    inside=False;finished=True;suffix.append(line);continue
                if line == b'      {\n': record=[]
                record.append(line)
                if line in (b'      },\n', b'      }\n'):
                    count += 1
                    blob=b''.join(record).rstrip().rstrip(b',')
                    if any(token in blob for token in [b'"path": "source/', b'"path": "universe/',
                            b'"path": "cache/surface_daily.parquet"', b'"path": "cache/underlying_daily.parquet"']):
                        retained.append(json.loads(blob))
                    record=[]
            else: suffix.append(line)
    if not finished or inside or not retained:
        raise ValueError('Unrecognized parent scope format')
    compact=b''.join(header)+json.dumps(retained).encode()[1:-1]+b'\n'+b''.join(suffix)
    doc=json.loads(compact)
    return doc,h.hexdigest(),count


def runtime():
    return {'python':sys.version, 'packages':{p:metadata.version(p) for p in RUNTIME_PACKAGES}}


def check_bound(scope):
    if runtime() != scope['runtime']: raise ValueError('Training runtime changed')
    for group in ['sources', 'inputs']:
        for path,digest in scope[group].items():
            p=ROOT/path
            if not p.is_file() or sha(p)!=digest:
                raise ValueError(f'Bound {group} changed: {path}')


def prepare(parent, campaign, reuse_completed=None, *, repair_neural=False):
    from nn_meta import config
    from nn_meta.feature_contract import CONTRACT_VERSION
    parent_base=ROOT/'nn_meta/campaigns'/parent/'v6'
    base=config.ARTIFACTS.parent
    scope_path=base/'continuation_scope.json'
    if scope_path.exists():
        scope=json.loads(scope_path.read_text())
        if (scope['parent'] != parent or scope.get('reuse_completed') != reuse_completed
                or scope.get('repair_neural', False) != repair_neural):
            raise ValueError('Continuation parent/reuse selection changed')
        check_bound(scope); return scope
    print('Verifying parent scope and completed symbol artifacts...',flush=True)
    old,digest,count=read_parent_scope(parent_base/'campaign_scope.json')
    if old['campaign']!=parent or old['pool']!='v6' or old['data_candidate']!=config.DATA_CANDIDATE:
        raise ValueError('Parent campaign identity mismatch')
    if old['feature_contract_version']!=CONTRACT_VERSION or old['window']!=[config.WINDOW_START,config.WINDOW_END]:
        raise ValueError('Parent feature contract or window mismatch')
    if old['strategies']!=config.PROPOSAL_STRATEGIES:
        raise ValueError('Parent proposal strategies changed')
    prep=ROOT/'nn_meta/expanded_inputs'/parent/'full-run'
    receipt=json.loads((prep/'worker-trial/result.json').read_text())
    if receipt != {'freeze_completed':True,'returncode':0}:
        raise ValueError('Parent freeze not complete')
    # The original launcher checks every worker and input fingerprint before
    # printing this line; assembly subsequently failed independently.
    if 'Completed build\n' not in (parent_base/'runs/next-stage/build.log').read_text():
        raise ValueError('Parent launcher has not verified build completion')
    config.ARTIFACTS.mkdir(parents=True,exist_ok=True)
    sources={};inputs={};changes={}
    for row in old['inputs']['files']:
        label=row['path']
        if label.startswith('source/'):
            rel=label.removeprefix('source/');p=ROOT/rel
            current=sha(p)
            if current!=row['sha256']:
                allowed = PERFORMANCE_CHANGES | (NEURAL_REPAIR_CHANGES if repair_neural else set())
                if rel not in allowed: raise ValueError(f'Unreviewed producer change: {rel}')
                changes[rel]={'parent':row['sha256'],'continuation':current}
            sources[rel]=current
        else:
            p=(config.DATA_CACHE/label.removeprefix('cache/') if label.startswith('cache/')
               else ROOT/'v3/artifacts'/label.removeprefix('universe/'))
            if sha(p)!=row['sha256']: raise ValueError(f'Assembly input changed since parent: {label}')
            inputs[str(p.relative_to(ROOT))]=row['sha256']
    for p in [config.SURFACE_DATASET_PARQUET,config.UNDERLYING_DAILY_PARQUET]:
        if str(p.relative_to(ROOT)) not in inputs: raise ValueError(f'Parent did not bind {p.name}')
    for rel in NEW_SOURCES: sources[rel]=sha(ROOT/rel)
    spec=json.loads((parent_base/'artifacts/baseline_spec.json').read_text())
    symbols=set(spec['symbols'])
    if set(p.stem for p in (parent_base/'artifacts/meta_rows').glob('*.parquet'))!=symbols:
        raise ValueError('Incomplete or extra parent symbol rows')
    if set(p.stem for p in (parent_base/'artifacts/meta_marks').glob('*.parquet'))!=symbols:
        raise ValueError('Incomplete or extra parent mark shards')
    files=[Path('baseline_spec.json')]
    for s in sorted(symbols):
        files += [Path('meta_rows')/f'{s}.parquet', Path('meta_rows')/f'{s}.provenance.json', Path('meta_marks')/f'{s}.parquet']
    for rel in files:
        original=parent_base/'artifacts'/rel;target=config.ARTIFACTS/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        h=sha(original)
        if target.exists() and sha(target)!=h: raise ValueError(f'Continuation artifact already differs: {rel}')
        if not target.exists(): shutil.copyfile(original,target)
        if sha(original)!=h or sha(target)!=h: raise ValueError(f'Artifact changed during copy: {rel}')
        inputs[str(target.relative_to(ROOT))]=h
    for p in [Path(config.V6_INPUTS), prep/'worker-trial/result.json']:
        inputs[str(p.relative_to(ROOT))]=sha(p)
    if inputs[str(Path(config.V6_INPUTS).relative_to(ROOT))] != config.V6_INPUTS_SHA256:
        raise ValueError('Expanded manifest digest changed')
    scope={'version':1,'campaign':campaign,'parent':parent,'parent_scope_sha256':digest,
        'reuse_completed':reuse_completed, 'repair_neural':repair_neural,
        'neural_preprocessing':'train-only-inactive-zero-v1',
        'parent_input_file_count':count,'feature_contract_version':CONTRACT_VERSION,
        'reuse':'Copied completed derived rows/marks. Raw option archives were not reread or revalidated.',
        'symbols':sorted(symbols),'sources':sources,'source_changes':changes,'inputs':inputs,'runtime':runtime(),
        'training':{'workers':int(os.environ['NN_META_TRAIN_WORKERS']),'threads':int(os.environ['NN_META_TRAIN_THREADS']),
                    'folds':3,'validation_days':40,'label':'label_excess','epochs':60,'trees':600,
                    'selection_seeds':[0,1,2,3,4],'final_seeds':list(config.SEEDS)},
        'experiments':['event_balanced_classifier','downside_q10'], 'research_only':True}
    check_bound(scope);write(scope_path,scope)
    return scope


def reuse_outputs(scope, records):
    """Import completed assembly/comparisons, never prior evaluation/bundles."""
    source=scope.get('reuse_completed')
    if not source:return
    from nn_meta import config
    base=ROOT/'nn_meta/campaigns'/source/'v6'
    old=json.loads((base/'continuation_scope.json').read_text())
    if (old['parent_scope_sha256']!=scope['parent_scope_sha256'] or old['runtime']!=scope['runtime']
            or old['feature_contract_version']!=scope['feature_contract_version']):
        raise ValueError('Completed-output lineage/runtime mismatch')
    training_only={'nn_meta/training_jobs.py','nn_meta/v4_evaluate.py',
                   'nn_meta/v4_finalize.py','scripts/continue_v6_training.py',
                   'nn_meta/neural_validation.py','nn_meta/v4_loader.py'}
    if scope.get('repair_neural'):
        training_only |= NEURAL_REPAIR_CHANGES
    for path,digest in scope['sources'].items():
        if path not in training_only and old['sources'].get(path)!=digest:
            raise ValueError(f'Assembly/comparison source changed: {path}')
    for path,digest in scope['inputs'].items():
        corresponding=path.replace(f'nn_meta/campaigns/{scope["campaign"]}/',f'nn_meta/campaigns/{source}/',1)
        if old['inputs'].get(corresponding)!=digest:
            raise ValueError(f'Assembly/comparison input changed: {path}')
    for stage,folder in [('assemble','artifacts'),('experiments','reports/objective-comparisons')]:
        destination=records/f'{stage}.json'
        if destination.exists():continue
        receipt_path=base/'runs/continuation'/f'{stage}.json'
        receipt=json.loads(receipt_path.read_text())
        if receipt.get('returncode')!=0 or not receipt.get('outputs'):
            raise ValueError(f'{source} has no completed {stage}')
        outputs={}
        for rel,digest in receipt['outputs'].items():
            origin=ROOT/rel
            if not origin.is_relative_to(base/folder) or sha(origin)!=digest:
                raise ValueError(f'Invalid completed output: {rel}')
            target=config.ARTIFACTS.parent/origin.relative_to(base)
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists() and sha(target)!=digest:raise ValueError(f'Conflicting output: {target.name}')
            if not target.exists():shutil.copyfile(origin,target)
            if sha(target)!=digest:raise ValueError('Copied output checksum mismatch')
            outputs[str(target.relative_to(ROOT))]=digest
        write(destination,{'returncode':0,'reused_from':source,
            'parent_receipt_sha256':sha(receipt_path),'parent_scope_sha256':sha(base/'continuation_scope.json'),
            'outputs':outputs})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent',type=name,required=True);p.add_argument('--campaign',type=name,required=True)
    p.add_argument('--workers',type=int,choices=[1,2,3,4],default=2)
    p.add_argument('--threads',type=int,choices=[1,2,3,4],default=2)
    p.add_argument('--reuse-completed',type=name,help='copy verified assembly/comparisons from a prior continuation')
    p.add_argument('--repair-neural',action='store_true',help='fresh scope with reviewed finite NN and inference/validation repairs; preserve old failed evidence')
    p.add_argument('--run',action='store_true');p.add_argument('--prepare-only',action='store_true')
    a=p.parse_args()
    if a.parent==a.campaign: raise ValueError('Continuation requires a new campaign name')
    if not a.run and not a.prepare_only:
        print(json.dumps({'preview':True,**vars(a),'stages':['assemble','experiments','evaluate','finalize'],
            'policy':'new output campaign; copied and verified parent shards; 3 post-freeze folds; research only'},indent=2));return
    resume=json.loads((ROOT/'nn_meta/expanded_inputs'/a.parent/'resume.json').read_text())
    env=resume['environment'];final=ROOT/'nn_meta/expanded_inputs'/a.parent/'full-run/final-inputs.json'
    env.update(NN_META_CAMPAIGN=a.campaign,NN_META_V6_INPUTS=str(final),
        NN_META_V6_INPUTS_SHA256=(final.with_suffix('.sha256')).read_text().strip(),
        NN_META_STREAM_ASSEMBLY='1',NN_META_PREPARED_TRAINING='1',NN_META_TRAIN_WORKERS=str(a.workers),
        NN_META_TRAIN_THREADS=str(a.threads),TF_NUM_INTRAOP_THREADS=str(a.threads),TF_NUM_INTEROP_THREADS='1',
        CUDA_VISIBLE_DEVICES='-1')
    os.environ.update(env)
    from nn_meta import config
    config.RUNS_DIR.mkdir(parents=True,exist_ok=True)
    with campaign_lock(config.RUNS_DIR/'.launcher.lock'):
        scope=prepare(a.parent,a.campaign,a.reuse_completed,repair_neural=a.repair_neural)
        if scope['training']['workers']!=a.workers or scope['training']['threads']!=a.threads:
            raise ValueError('Continuation resource plan changed')
        if a.prepare_only: return
        marks=str(config.ARTIFACTS/'meta_dataset.marks.parquet')
        commands={
            'assemble':['nn_meta.build_meta_dataset','--assemble','--membership'],
            'experiments':['nn_meta.training_experiments','--threads',str(a.threads)],
            'evaluate':['nn_meta.v4_evaluate','--dataset',str(config.META_DATASET_PARQUET),
                        '--marks',marks,'--folds','3','--post-freeze-folds','--output',str(config.REPORTS_DIR/'evaluate.md')],
            'finalize':['nn_meta.v4_finalize','--marks',marks]}
        records=config.RUNS_DIR/'continuation';records.mkdir(exist_ok=True)
        reuse_outputs(scope,records)
        for stage,args in commands.items():
            check_bound(scope)
            result_path=records/f'{stage}.json'
            if result_path.exists():
                previous=json.loads(result_path.read_text())
                if previous.get('returncode')==0 and previous.get('outputs'):
                    if not all((ROOT/n).is_file() and sha(ROOT/n)==h for n,h in previous['outputs'].items()):
                        raise ValueError(f'Completed {stage} outputs changed')
                    print(f'Resume verified stage {stage}',flush=True);continue
            start=time.time();command=[sys.executable,'-m',*args]
            write(records/'latest.json',{'campaign':a.campaign,'stage':stage,'status':'running','started':start})
            print(f'Start {stage}',flush=True)
            with (records/f'{stage}.log').open('a') as log:
                result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            check_bound(scope)
            if stage=='assemble': paths=[config.META_DATASET_PARQUET,Path(marks),config.META_DATASET_PARQUET.with_suffix('.assembly.json')]
            elif stage=='experiments': paths=list((config.REPORTS_DIR/'objective-comparisons').glob('*'))
            elif stage=='evaluate': paths=list(config.REPORTS_DIR.glob('evaluate*'))
            else: paths=list(config.V4_MODEL_FINAL_DIR.rglob('*'))+list(config.REPORTS_DIR.glob('*final*'))
            outputs={str(q.relative_to(ROOT)):sha(q) for q in paths if q.is_file()}
            write(result_path,{'command':command,'returncode':result.returncode,'seconds':time.time()-start,'outputs':outputs})
            if result.returncode:
                write(records/'latest.json',{'campaign':a.campaign,'stage':stage,'status':'failed','returncode':result.returncode})
                raise SystemExit(result.returncode)
            print(f'Completed {stage}',flush=True)
        write(records/'latest.json',{'campaign':a.campaign,'status':'complete','finished':time.time()})


if __name__=='__main__':
    main()
