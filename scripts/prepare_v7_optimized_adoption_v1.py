#!/usr/bin/env python3
"""Prepare a successor view without modifying original waves or their seals."""
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.run_v7_optimized_campaign_v1 import read,prepare
from scripts.finish_v7_optimized_inputs_v1 import STATE,OLD,save_config
from nn_meta.v7.storage import sha
from incubator.continual.storage import write


def main():
    v=ROOT/'nn_meta/validation';parent=v/'v7-execution-campaign-20260928-r1'
    STATE.mkdir(exist_ok=True)
    args=dict(plan=str(v/'v7-full-execution-plan-20260928'),
        **{'base-index':str(v/'v7-frontier-quote-index-20260928-r4'),
           'entry-root':str(ROOT/'nn_meta/data_v7/entry-campaign-20260927')},
        references=str(v/'v7-reference-reconciliation-20260928-full-r0'),
        review=str(v/'v7-reference-rename-review-20260928'),hours=str(v/'v7-dated-hours-20260927'),
        blackouts=str(v/'v7-contract-blackouts-20260928-approved'))
    config=dict(mode='discovery',arguments=args,securities=read(parent/'declaration.json')['securities'],
        parent=str(parent),exclusive_roots=[str(parent),str(v/'v7-execution-recovery-20260929-r0')],
        empty_roots=[str(v/'v7-execution-recovery-20260929-r0/empty')])
    save_config(STATE/'discovery-config.json',config)
    # Complete immutable capture artifacts are retained at their original paths.
    epoch=STATE/'epochs/00001';epoch.mkdir(parents=True,exist_ok=True)
    for name in ['selection.json','raw','frontier','capture','replay-plan']:
        target=OLD/'epochs/00001'/name;link=epoch/name
        if not link.exists():link.symlink_to(target,target_is_directory=target.is_dir())
    oldreplay=OLD/'epochs/00001/replay'
    rconfig=dict(mode='replay',arguments=read(oldreplay/'declaration.json')['arguments'],
        securities=read(oldreplay/'declaration.json')['securities'],parent=str(oldreplay),exclusive_roots=[str(oldreplay)])
    save_config(epoch/'optimized-replay-config.json',rconfig)
    adoption=dict(schema='v7-performance-adoption-v1',authorization='2026-10-02 user: ok lets do it; integrate, verify and resume',
        predecessor=str(OLD),discovery_parent=str(parent),replay_parent=str(oldreplay),
        discovery_campaign=str(STATE/'discovery-campaign'),
        checkpoint_policy='reflink verified physical copies for unfinished waves; originals retained; completed waves reused',
        storage_policy=dict(clone='reflink-always',write_reserve_bytes=20_000_000_000,fail_if_clone_unsupported=True),
        worker_policy=dict(discovery_day_max=2,discovery_night_max=4,replay_max=1,worker_mib=3072,day_reserve_mib=18432,night_reserve_mib=12288),
        parent_declarations={str(p):sha(p) for p in [parent/'declaration.json',oldreplay/'declaration.json']})
    save_config(STATE/'adoption.json',adoption)
    for state,cp in [(STATE/'discovery-campaign',STATE/'discovery-config.json'),(epoch/'replay',epoch/'optimized-replay-config.json')]:
        # The CLI owns predecessor/controller locks for preparation too.
        import subprocess
        subprocess.run([sys.executable,str(ROOT/'scripts/run_v7_optimized_campaign_v1.py'),'--state',str(state),'--config',str(cp),'--prepare-only'],check=True)
        if not (state/'progress.json').exists():
            mode=read(cp)['mode'];waves=list((state/'waves').glob('*/progress.json'))
            terminal='discovered' if mode=='discovery' else 'replayed_pending'
            n=sum(read(p).get('status')==terminal for p in waves)+len(list((state/'empty').iterdir()))
            write(state/'progress.json',dict(status='checkpointed',securities_required=len(read(cp)['securities']),
                securities_discovered=n if mode=='discovery' else None,securities_replayed=n if mode=='replay' else None,
                active_securities=[],failed_securities={},full_execution_coverage=False))
    print(json.dumps(dict(state=str(STATE),free_bytes=shutil.disk_usage(ROOT).free)))

if __name__=='__main__':main()
