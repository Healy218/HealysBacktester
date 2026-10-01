#!/usr/bin/env python3
"""Anchor the completed r3 data for an append-only two-session daily update."""
import json
from pathlib import Path
import sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from incubator.continual.storage import sha,identity,verify,write
from incubator.daily_v6.snapshot import extend_snapshot


def main():
    old=json.loads((ROOT/'deploy/incubator-continual-v6-r3.json').read_text())
    parent=Path(old['root']);target=ROOT/'incubator/continual-v6/r4'
    if (target/'contract.json').exists():raise ValueError('Daily lineage already started')
    completed=parent/'runs/2026-09-28';verify(completed/'candidate')
    declaration=json.loads((completed/'declaration.json').read_text())
    prefix=Path(declaration['snapshot'])
    if sha(prefix/'manifest.json')!=declaration['snapshot_sha256']:raise ValueError('Prior completed snapshot changed')
    fresh=parent/'snapshots/2026-09-30'
    snapshot=target/'snapshots/2026-09-30'
    if not (snapshot/'manifest.json').exists():extend_snapshot(prefix,fresh,snapshot)
    contract=json.loads((parent/'contract.json').read_text())
    anchors={};count=0
    for tree in ['features','labels']:
        for path in sorted((parent/tree).glob('**/complete.json')):
            header=verify(path.parent)
            if header['declaration']['contract']!=identity(contract):raise ValueError('Mixed parent contract')
            anchors[str(path.relative_to(parent))]=sha(path);count+=1
            if count%10000==0:print(f'Verified {count} parent seals',flush=True)
    census=target/'inherited-r3.json'
    write(census,dict(root=str(parent),contract_identity=identity(contract),anchors=anchors,
          ancestor=old['inherited_artifacts'],created_at=datetime.now(timezone.utc).isoformat(),
          completed_candidate_sha256=sha(completed/'candidate/complete.json')))
    config=dict(old,root=str(target),lineage=dict(revision='r4',previous_root=str(parent),
          reason='Preserve frozen stock prefixes, append only later bars, and retain r3/r2 feature and label seals by reference.'),
          comparison_candidate=dict(path=str(completed/'candidate'),sha256=sha(completed/'candidate/complete.json'),through='2026-09-28',verdict='rejected'),
          prefix_snapshot=dict(path=str(prefix),sha256=sha(prefix/'manifest.json'),through='2026-09-28'),
          bootstrap_snapshot=dict(path=str(snapshot),sha256=sha(snapshot/'manifest.json'),through='2026-09-30'),
          inherited_artifacts=dict(path=str(census),sha256=sha(census)),repair_priority=[])
    write(ROOT/'deploy/incubator-continual-v6-r4.json',config)
    evidence=ROOT/'nn_meta/validation/v6-daily-update-20260930-r4'
    write(evidence/'preparation.json',dict(prepared_at=datetime.now(timezone.utc).isoformat(),
          prior_candidate=str(completed/'candidate'),prior_candidate_sha256=sha(completed/'candidate/complete.json'),
          frozen_through='2026-09-28',target_through='2026-09-30',parent_seals=count,
          config_sha256=sha(ROOT/'deploy/incubator-continual-v6-r4.json'),snapshot_sha256=sha(snapshot/'manifest.json')))
    print(json.dumps(dict(prepared=True,parent_seals=count,root=str(target))),flush=True)


if __name__=='__main__':main()
