#!/usr/bin/env python3
"""Bind retained r2 checkpoints for an explicit, non-mutating r3 continuation."""
import json
from pathlib import Path
import sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from incubator.continual.storage import sha,identity,verify,write


def main():
    original=json.loads((ROOT/'deploy/incubator-continual-v6-r2.json').read_text())
    parent=Path(original['root']);target=ROOT/'incubator/continual-v6/r3'
    if (target/'contract.json').exists():raise ValueError('r3 already started; never regenerate its inheritance')
    contract=json.loads((parent/'contract.json').read_text())
    for name,digest in contract['sources'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Parent source drift: '+name)
    status=json.loads((parent/'latest-run.json').read_text())
    run=json.loads((parent/'runs'/status['through']/'declaration.json').read_text())
    if run['contract_identity']!=identity(contract):raise ValueError('Parent contract differs')
    if sha(Path(run['snapshot'])/'manifest.json')!=run['snapshot_sha256']:raise ValueError('Snapshot changed')
    anchors={};counts={}
    for tree in ['features','labels','runs/'+status['through']+'/symbols']:
        paths=sorted((parent/tree).glob('**/complete.json'));counts[tree]=len(paths)
        for path in paths:
            header=verify(path.parent)
            if header['declaration']['contract']!=identity(contract):raise ValueError('Mixed parent artifact lineage')
            anchors[str(path.relative_to(parent))]=sha(path)
    history={p.stem:sha(p) for p in sorted((parent/'history').glob('*.json'))}
    document=dict(schema='v6-continual-inheritance-v1',root=str(parent),contract_identity=identity(contract),
        contract_sha256=sha(parent/'contract.json'),through=run['through'],snapshot_sha256=run['snapshot_sha256'],
        anchors=anchors,history=history,counts=counts,created_at=datetime.now(timezone.utc).isoformat())
    path=target/'inherited-r2.json';write(path,document)
    config={**original,'root':str(target),'lineage':dict(revision='r3',previous_root=str(parent),
        reason='Preserve colliding frozen proposal occurrences; bounded transient tick retries; reference verified r2 successes without relabeling.'),
        'bootstrap_snapshot':dict(path=run['snapshot'],sha256=run['snapshot_sha256'],through=run['through']),
        'inherited_artifacts':dict(path=str(path),sha256=sha(path)),
        'repair_priority':[e['symbol'] for e in status.get('errors',[])]}
    write(ROOT/'deploy/incubator-continual-v6-r3.json',config)
    print(json.dumps(dict(counts=counts,repair_priority=config['repair_priority'],inheritance_sha256=sha(path))))

if __name__=='__main__':main()
