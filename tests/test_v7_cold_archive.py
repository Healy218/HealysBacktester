import json
import os
from pathlib import Path
import subprocess

import pytest

from scripts import archive_v7_cold as cold
from scripts.verify_v7_cold_archive import verify
from scripts import archive_v7_cold_parallel as parallel


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
