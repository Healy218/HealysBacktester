import json
from pathlib import Path

import pytest

from scripts import v6_focus_workers_20260930 as workers


def test_worker_budget_increases_concurrency_without_exceeding_memory():
    plan=workers.resource_plan(3584,available_workers=16,cpus=16)
    assert plan['workers']==6
    assert plan['workers']*plan['worker_mib']+plan['parent_reserve_mib']<=plan['memory_max_mib']
    assert workers.resource_plan(3584,available_workers=4,cpus=16)['workers']==4
    with pytest.raises(ValueError,match='floor'):
        workers.resource_plan(1024,available_workers=16,cpus=16)


def test_prepare_cannot_interrupt_training(tmp_path,monkeypatch):
    (tmp_path/'latest-run.json').write_text(json.dumps(dict(training_started=True,stage='training')))
    monkeypatch.setattr(workers.focus,'preflight',lambda:({'root':str(tmp_path)},'2026-09-28',None))
    with pytest.raises(ValueError,match='data stage'):
        workers.prepare()


def test_snapshot_contains_only_completed_symbols(tmp_path):
    symbols=tmp_path/'runs/2026-09-28/symbols'
    (symbols/'SPY').mkdir(parents=True)
    (symbols/'QQQ').mkdir()
    receipt=symbols/'SPY/complete.json';receipt.write_text('{}')
    (symbols/'QQQ/inventory.json').write_text('{}')
    assert workers.snapshot({'root':str(tmp_path)},'2026-09-28')=={str(receipt):workers.sha(receipt)}
