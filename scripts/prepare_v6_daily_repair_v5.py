#!/usr/bin/env python3
"""Bind r5 to the failed r4 run and its unchanged, verified successful artifacts."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from incubator.continual.storage import sha, identity, verify, write
from scripts.run_v6_continual_v4 import runtime_sources


def main():
    oldroot = ROOT/'incubator/continual-v6/r4'
    newroot = ROOT/'incubator/continual-v6/r5'
    state = ROOT/'nn_meta/validation/v6-daily-repair-20261001-r5'
    if (newroot/'inherited-r4.json').exists():
        raise ValueError('Preparation already bound; inspect existing receipts')
    config = json.loads((ROOT/'deploy/incubator-continual-v6-r4.json').read_text())
    run = json.loads((oldroot/'latest-run.json').read_text())
    if run['status'] != 'blocked' or run['through'] != '2026-09-30' or run['symbols_complete'] != 447:
        raise ValueError('Unexpected stopped r4 run')
    if {e['symbol'] for e in run['errors']} != {'CRSP','MTUM'}:
        raise ValueError('Unexpected repair scope')
    contract = json.loads((oldroot/'contract.json').read_text())
    if contract['sources'] != runtime_sources() or identity(contract) != run['contract_identity']:
        raise ValueError('Original r4 producer changed')
    write(state/'failed-r4-run.json', run)
    write(state/'failed-r4-service-exit.json', json.loads((oldroot/'service-exit.json').read_text()))
    anchors = {}; counts = {}
    for category in ['features','labels','runs/2026-09-30/symbols']:
        paths = sorted((oldroot/category).rglob('complete.json'))
        counts[category] = len(paths)
        for p in paths:
            header = verify(p.parent)
            if header['declaration']['contract'] != run['contract_identity']:
                raise ValueError('Unexpected producer in r4 census')
            anchors[str(p.relative_to(oldroot))] = sha(p)
        print(json.dumps(dict(verified=category,count=len(paths))), flush=True)
    if counts['runs/2026-09-30/symbols'] != 447:
        raise ValueError('Completed symbol count differs')
    history = {p.stem:sha(p) for p in (oldroot/'history').glob('*.json')}
    census = dict(root=str(oldroot), contract_identity=run['contract_identity'], anchors=anchors,
                  history=history, ancestor=config['inherited_artifacts'], counts=counts,
                  created_at=datetime.now(timezone.utc).isoformat())
    write(newroot/'inherited-r4.json', census)
    newconfig = dict(config, root=str(newroot), inherited_artifacts=dict(path=str(newroot/'inherited-r4.json'),
        sha256=sha(newroot/'inherited-r4.json')), reuse_contract=dict(path=str(oldroot/'contract.json'),
        sha256=sha(oldroot/'contract.json')), repair_priority=['CRSP','MTUM'],
        lineage=dict(revision='r5',previous_root=str(oldroot),
            reason='Append new historical proposal occurrences as separate immutable batches; reference unchanged r4 completed symbols and original feature/label seals.'))
    write(ROOT/'deploy/incubator-continual-v6-r5.json', newconfig)
    write(state/'prepared.json',dict(created_at=datetime.now(timezone.utc).isoformat(),
        config_sha256=sha(ROOT/'deploy/incubator-continual-v6-r5.json'),counts=counts,
        parent_symbol_seals={k:v for k,v in anchors.items() if k.startswith('runs/')},
        pause_plan=str(ROOT/'nn_meta/validation/v6-daily-update-20260930-r4/dedicated/pause-plan.json')))
    # restore() resolves collected transient services beneath its own STATE.
    old_units = ROOT/'nn_meta/validation/v6-daily-update-20260930-r4/dedicated/units'
    unit_hashes = {}
    for source in old_units.glob('*.service'):
        target = state/'units'/source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        unit_hashes[source.name] = sha(target)
    write(state/'restoration-unit-bindings.json',dict(source=str(old_units),files=unit_hashes))
    print(json.dumps(dict(prepared=True,root=str(newroot),counts=counts)),flush=True)


if __name__ == '__main__':
    main()
