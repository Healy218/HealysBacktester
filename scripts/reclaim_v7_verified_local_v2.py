#!/usr/bin/env python3
"""Versioned completion-status repair for the frozen early-cleanup consumer.

Retains all v1 eligibility, checksum, process-coordination and journal behavior.
Only the duplicate completion timestamp keyword is corrected.
"""
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import reclaim_v7_verified_local as base


def status(state, **values):
    payload = dict(values)
    payload.update(status=state, at=base.cold.now())
    base.cold.save(base.cold.STATE / 'early-cleanup-progress.json', payload)


def main():
    if '--resume-controller' not in sys.argv:
        cold = base.cold
        cold.drive()
        binding = dict(schema='v7-early-cleanup-status-recovery-v2',
                       source_sha256=cold.archive.sha(Path(__file__)),
                       parent_source_sha256=cold.archive.sha(Path(base.__file__)),
                       plan_sha256=cold.archive.sha(cold.STATE / 'plan.json'))
        path = cold.STATE / 'early-cleanup-consumer-v2.json'
        if path.exists() and json.loads(path.read_text()) != binding:
            raise ValueError('Early cleanup recovery consumer changed')
        cold.save(path, binding)
        cold.save(cold.DEST / 'manifests' / path.name, binding)
        shutil.copy2(__file__, cold.DEST / 'manifests/reclaim_v7_verified_local_v2.py')
    base.status = status
    base.main()


if __name__ == '__main__':
    main()
