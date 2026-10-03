import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import time
from contextlib import nullcontext

import pytest

from scripts import archive_v7_cold as cold
from scripts.verify_v7_cold_archive import verify
from scripts import archive_v7_cold_parallel as parallel
from scripts import archive_v7_cold_staged as staged
from scripts import reclaim_v7_verified_local as early
from scripts import reclaim_v7_verified_local_v2 as early_v2


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    state = root / 'nn_meta/validation/v7-cold-archive-test'
    dest = tmp_path / 'external'
    source = root / 'nn_meta/validation/v7-test'
    for p in (state, dest / 'data', dest / 'manifests', source):
        p.mkdir(parents=True)
    monkeypatch.setattr(cold, 'ROOT', root)
    monkeypatch.setattr(cold, 'STATE', state)
    monkeypatch.setattr(cold, 'DEST', dest)
    monkeypatch.setattr(cold, 'drive', lambda: None)
    monkeypatch.setattr(cold.archive, 'ROOT', Path('/'))
    payload = source / 'checkpoint.bin'
    payload.write_bytes(b'checkpoint-evidence\0' * 70000)
    (source / 'receipt.json').write_text('{"preserve": true}\n')
    (source / 'link').symlink_to('checkpoint.bin')
    os.link(payload, source / 'alias.bin')
    group = dict(id='00000', members=[cold.relative(source)], shallow=[])
    plan = dict(groups=[group])
    cold.save(state / 'plan.json', plan)
    return source, state, dest, group, plan


def authorize(state, dest):
    cold.save(dest / 'VERIFIED.json', dict(plan_sha256=cold.archive.sha(state / 'plan.json')))


def test_roundtrip_and_verified_retirement_preserve_small_files_and_links(sandbox, tmp_path):
    source, state, dest, group, plan = sandbox
    result = cold.pack(group, 1)
    assert result['members'] == dict(files=3, directories=1, symlinks=1)
    restored = tmp_path / 'restored'
    restored.mkdir()
    subprocess.run(['tar', '-I', 'zstd -d', '-xf', str(dest / 'data/00000.tar.zst'),
                    '-C', str(restored)], check=True)
    copy = restored / cold.relative(source)
    assert (copy / 'checkpoint.bin').read_bytes() == (source / 'checkpoint.bin').read_bytes()
    assert os.readlink(copy / 'link') == 'checkpoint.bin'
    assert (copy / 'alias.bin').stat().st_ino == (copy / 'checkpoint.bin').stat().st_ino
    authorize(state, dest)
    assert cold.retire(plan) == 2
    assert not (source / 'checkpoint.bin').exists()
    assert (source / 'receipt.json').is_file()
    assert (source / 'link').is_symlink()
    assert cold.retire(plan) == 2


def test_corrupt_archive_blocks_reuse_and_retirement(sandbox):
    source, state, dest, group, plan = sandbox
    cold.pack(group, 1)
    with (dest / 'data/00000.tar.zst').open('ab') as f:
        f.write(b'corrupt')
    with pytest.raises(ValueError, match='archive changed'):
        cold.pack(group, 1)
    authorize(state, dest)
    with pytest.raises(ValueError, match='Archive changed'):
        cold.retire(plan)
    assert (source / 'checkpoint.bin').exists()


def test_changed_source_blocks_retirement(sandbox):
    source, state, dest, group, plan = sandbox
    cold.pack(group, 1)
    with (source / 'checkpoint.bin').open('r+b') as f:
        f.write(b'changed')
    authorize(state, dest)
    with pytest.raises(ValueError, match='Source changed'):
        cold.retire(plan)
    assert (source / 'checkpoint.bin').exists()


def test_retirement_requires_global_verification(sandbox):
    source, state, dest, group, plan = sandbox
    cold.pack(group, 1)
    with pytest.raises(FileNotFoundError):
        cold.retire(plan)
    assert (source / 'checkpoint.bin').exists()


def test_external_symlink_is_preserved_without_archiving_target(sandbox, tmp_path):
    source, state, dest, group, plan = sandbox
    outside = tmp_path / 'shared.bin'
    outside.write_bytes(b'shared-evidence' * 100000)
    (source / 'external').symlink_to(outside)
    result = cold.pack(group, 1)
    assert result['members']['symlinks'] == 2
    assert all(x['path'] != cold.relative(outside) for x in result['retire_candidates'])
    authorize(state, dest)
    cold.retire(plan)
    assert outside.exists()


def test_restore_helper_checks_actual_archives(sandbox, capsys):
    source, state, dest, group, plan = sandbox
    result = cold.pack(group, 1)
    (dest / 'manifests/plan.json').write_bytes((state / 'plan.json').read_bytes())
    cold.save(dest / 'VERIFIED.json', dict(plan_sha256=cold.archive.sha(state / 'plan.json'),
                                          groups=1, archive_bytes=result['archive_bytes']))
    assert verify(dest) == 1
    assert 'tar -I zstd -xf data/00000.tar.zst' in capsys.readouterr().out
    (dest / 'data/00000.tar.zst').write_bytes(b'bad')
    with pytest.raises(ValueError, match='checksum/size mismatch'):
        verify(dest)


def test_plan_freezes_scope_and_source(sandbox, monkeypatch):
    source, state, dest, group, plan = sandbox
    monkeypatch.setattr(cold, 'source_roots', lambda: [source])
    plan = cold.make_plan()
    cold.validate_plan(plan)
    assert plan['groups'][0]['members'] == [cold.relative(source)]
    plan['source_script_sha256'] = 'changed'
    with pytest.raises(ValueError, match='source changed'):
        cold.validate_plan(plan)


def test_parallel_groups_have_independent_verified_outputs(sandbox):
    source, state, dest, group, plan = sandbox
    second = source.parent / 'v7-second'
    second.mkdir()
    (second / 'evidence.txt').write_text('independent evidence')
    other = dict(id='00001', members=[cold.relative(second)], shallow=[])
    results = parallel.execute_groups([group, other], 2)
    assert {r['id'] for r in results} == {'00000', '00001'}
    assert (state / '00000.verified.json').exists()
    assert (state / '00001.verified.json').exists()
    assert (source / 'checkpoint.bin').exists()


def test_parallel_failure_admits_no_later_work(sandbox, monkeypatch):
    seen = []
    def broken(group, threads):
        seen.append(group['id'])
        raise ValueError('integrity failure')
    monkeypatch.setattr(cold, 'pack', broken)
    with pytest.raises(ValueError, match='integrity failure'):
        parallel.execute_groups([{'id': 'first'}, {'id': 'second'}], 1)
    assert seen == ['first']


def test_staged_archive_retains_original_verification_and_reclaims_only_later(sandbox, monkeypatch):
    source, state, dest, group, plan = sandbox
    monkeypatch.setattr(staged, 'LOCAL_RESERVE', 0)
    budget = staged.Budget(64 * 1024**2)
    result = staged.pack_staged(group, budget)
    assert result['consumer'] == 'staged-v2'
    assert result['members'] == dict(files=3, directories=1, symlinks=1)
    assert not list((state / 'staging').iterdir())
    assert budget.used == 0
    assert (source / 'checkpoint.bin').exists()
    authorize(state, dest)
    assert cold.retire(plan) == 2


def test_staged_copy_corruption_blocks_publication(sandbox, monkeypatch):
    source, state, dest, group, plan = sandbox
    monkeypatch.setattr(staged, 'LOCAL_RESERVE', 0)
    original = staged.transfer
    def corrupt(stage, partial):
        original(stage, partial)
        with partial.open('ab') as f:
            f.write(b'bad')
    monkeypatch.setattr(staged, 'transfer', corrupt)
    budget = staged.Budget(64 * 1024**2)
    with pytest.raises(ValueError, match='transfer checksum mismatch'):
        staged.pack_staged(group, budget)
    assert not (state / '00000.verified.json').exists()
    assert not (dest / 'data/00000.tar.zst').exists()
    assert (source / 'checkpoint.bin').exists()
    assert budget.used == 0


def test_staged_capacity_defers_without_changing_source(sandbox):
    source, state, dest, group, plan = sandbox
    assert staged.pack_staged(group, staged.Budget(1024)) is None
    assert (source / 'checkpoint.bin').exists()
    assert not (state / '00000.verified.json').exists()


def test_staged_source_change_blocks_publication(sandbox, monkeypatch):
    source, state, dest, group, plan = sandbox
    monkeypatch.setattr(staged, 'LOCAL_RESERVE', 0)
    original = staged.compress
    def mutate(*args):
        original(*args)
        (source / 'receipt.json').write_text('changed')
    monkeypatch.setattr(staged, 'compress', mutate)
    with pytest.raises(ValueError, match='Source changed'):
        staged.pack_staged(group, staged.Budget(64 * 1024**2))
    assert not (state / '00000.verified.json').exists()


@pytest.fixture
def early_sandbox(sandbox, monkeypatch):
    source, state, dest, group, plan = sandbox
    cold.pack(group, 1)
    plan['roots'] = [cold.relative(source)]
    plan['groups'].append(dict(id='99999', members=['run/media/healy/MRHA/remaining'], shallow=[]))
    cold.save(state / 'plan.json', plan)
    cold.save(dest / 'manifests/plan.json', plan)
    cold.save(state / 'progress.json', dict(status='archiving', phase='serial-direct', active_groups=['99999']))
    monkeypatch.setattr(cold, 'validate_plan', lambda plan: None)
    monkeypatch.setattr(early, 'status', early_v2.status)
    class FakeController:
        def __init__(self, pid):
            pass
        def pause(self):
            return nullcontext()
        def close(self):
            pass
    monkeypatch.setattr(early, 'Controller', FakeController)
    monkeypatch.setattr(early.subprocess, 'check_output', lambda *a, **k: '123')
    return sandbox


def test_early_cleanup_does_not_require_or_fabricate_full_completion(early_sandbox):
    source, state, dest, group, plan = early_sandbox
    early.run(0)
    assert not (source / 'checkpoint.bin').exists()
    assert (source / 'receipt.json').is_file()
    assert (source / 'link').is_symlink()
    assert (state / 'LOCAL_CLEANUP_COMPLETE.json').exists()
    assert not (state / 'VERIFIED.json').exists()
    assert not (state / 'COMPLETE.json').exists()
    assert len((state / 'retired.jsonl').read_text().splitlines()) == 2
    # Later original final cleanup consumes exactly the same journal entries.
    plan['groups'] = [group]
    cold.save(state / 'plan.json', plan)
    authorize(state, dest)
    assert cold.retire(plan) == 2


def test_early_cleanup_rejects_corrupt_external_copy(early_sandbox):
    source, state, dest, group, plan = early_sandbox
    with (dest / 'data/00000.tar.zst').open('ab') as f:
        f.write(b'corrupted')
    with pytest.raises(ValueError, match='External archive changed'):
        early.run(0)
    assert (source / 'checkpoint.bin').exists()


def test_early_cleanup_hands_off_before_final_reclamation(early_sandbox):
    source, state, dest, group, plan = early_sandbox
    cold.save(state / 'VERIFIED.json', {})
    with pytest.raises(early.FinalPhase):
        early.phase_guard(plan)
    assert (source / 'checkpoint.bin').exists()


def test_early_cleanup_requires_all_local_receipts(early_sandbox):
    source, state, dest, group, plan = early_sandbox
    plan['groups'].append(dict(id='missing', members=[cold.relative(source.parent / 'v7-missing')], shallow=[]))
    with pytest.raises(FileNotFoundError):
        early.local_manifest(plan)


def test_early_cleanup_preserves_frozen_root_files(early_sandbox):
    source, state, dest, group, plan = early_sandbox
    receipt = json.loads((state / '00000.verified.json').read_text())
    item = receipt['retire_candidates'][0]
    plan['roots'].append(item['path'])
    assert early.candidate_path(item, group, plan) is None


def test_controller_guard_and_crash_recovery(sandbox):
    source, state, dest, group, plan = sandbox
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    controller = early.Controller(child.pid, expected=None)
    try:
        with controller.pause():
            assert early.identity(child.pid)['state'] == 'T'
            assert early.marker().exists()
        assert not early.marker().exists()
        cold.save(early.marker(), early.identity(child.pid))
        os.kill(child.pid, signal.SIGSTOP)
        deadline = time.monotonic() + 5
        while early.identity(child.pid)['state'] != 'T' and time.monotonic() < deadline:
            time.sleep(.005)
        assert early.identity(child.pid)['state'] == 'T'
        early.recover_pause(expected=None)
        assert not early.marker().exists()
        # SIGCONT is asynchronous; allow acknowledgement before the next guard.
        while early.identity(child.pid)['state'] == 'T' and time.monotonic() < deadline:
            time.sleep(.005)
        assert early.identity(child.pid)['state'] != 'T'
    finally:
        os.kill(child.pid, signal.SIGCONT)
        child.terminate(); child.wait(); controller.close()
