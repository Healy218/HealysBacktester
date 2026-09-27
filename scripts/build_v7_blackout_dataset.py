"""Build proposal/DTE shards with a mandatory sealed contract/date blackout policy.

Input manifests name captured dependencies; no downloads or model training occur
in this command. The resulting shard list feeds prepare_v7_training_fold.py.
Unresolved outcomes stay in each partition's census and do not imply readiness.
"""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def work(payload):
    manifest,minutes,output,chunk_size,blackouts = payload
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.dataset_inputs import load_worker
    from nn_meta.v7.assembly import assemble
    from nn_meta.v7.contract_blackouts import BlackoutPolicy, BlackoutObservedOptions
    import resource
    import time
    began = time.monotonic()
    join,engine,inputs = load_worker(manifest,minutes)
    engine = BlackoutObservedOptions(engine,BlackoutPolicy(blackouts))
    from nn_meta.v7.storage import sha
    inputs = {**inputs, **engine.inputs, str(Path(__file__).resolve()):sha(__file__)}
    result = assemble(Path(output)/join.proposals.declaration['security_id']/str(minutes),
        join,engine,inputs=inputs,reserve_bytes=100*1024**3,proposals_per_chunk=chunk_size)
    report = dict(security_id=join.proposals.declaration['security_id'],minutes=minutes,
        counts=result['counts'],statuses=result['statuses'],shards=result['shards'],
        seconds=time.monotonic()-began,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    print(json.dumps(report),flush=True)
    return report


def main():
    from nn_meta.v7.runtime import worker_pool
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,action='append',required=True)
    parser.add_argument('--blackouts',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,required=True)
    parser.add_argument('--proposals-per-chunk',type=int,default=512)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta'):
        raise ValueError('Repository artifact disk required')
    if len({p.resolve() for p in args.manifest})!=len(args.manifest):
        raise ValueError('Duplicate dataset manifest')
    roots = [Path(json.loads(p.read_text())['proposal_root']).resolve() for p in args.manifest]
    if len(set(roots))!=len(roots):raise ValueError('Duplicate security proposal root')
    jobs = [(p,m,args.output,args.proposals_per_chunk,args.blackouts) for p in args.manifest for m in (5,15,30)]
    with worker_pool(args.workers,threads=1) as pool:
        reports = list(pool.map(work,jobs))
    from nn_meta.v7.storage import sha,identity,verify,receipt,transaction
    partitions = {str(args.output/r['security_id']/str(r['minutes'])/'summary/complete.json'):
                  sha(args.output/r['security_id']/str(r['minutes'])/'summary/complete.json') for r in reports}
    declaration = dict(schema='v7-blackout-assembly-index-v1',partitions=partitions,
        blackouts=str(args.blackouts.resolve()),blackout_receipt_sha256=sha(args.blackouts/'complete.json'),
        manifests={str(p.resolve()):sha(p) for p in args.manifest},timeframes=[5,15,30])
    target = args.output/'index'
    if target.exists():verify(target,expected_identity=identity(declaration))
    else:
        with transaction(target) as temp:
            (temp/'declaration.json').write_text(json.dumps(declaration,indent=2)+'\n')
            (temp/'shards.json').write_text(json.dumps([p for r in reports for p in r['shards']],indent=2)+'\n')
            receipt(temp,dict(identity=identity(declaration),research_ready=False))
    print(json.dumps(dict(partitions=reports,shards=str(target/'shards.json'),
                          research_ready=False,training_launched=False)),flush=True)


if __name__=='__main__':main()
