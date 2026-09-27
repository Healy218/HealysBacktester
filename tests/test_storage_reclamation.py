import errno
import hashlib
import json
import os
import subprocess

import pytest

from scripts.reclaim_verified_duplicates import replace_copy
from scripts import archive_v6_inputs


def test_reflink_keeps_content_metadata_and_independent_writes(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    data = b'preserved history' * 4096
    a.write_bytes(data); b.write_bytes(data); b.chmod(0o640)
    old_mtime = b.stat().st_mtime_ns
    try:
        replace_copy(a, b, hashlib.sha256(data).hexdigest(), len(data))
    except OSError as exc:
        if exc.errno == errno.EOPNOTSUPP:
            pytest.skip('Test filesystem does not support reflinks')
        raise
    assert a.stat().st_ino != b.stat().st_ino
    assert b.read_bytes() == data
    assert b.stat().st_mode & 0o777 == 0o640
    assert b.stat().st_mtime_ns == old_mtime
    b.write_bytes(b'new independent data')
    assert a.read_bytes() == data


def test_changed_duplicate_is_not_replaced(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.write_bytes(b'original'); b.write_bytes(b'mutation')
    inode = b.stat().st_ino
    with pytest.raises(ValueError, match='Content changed'):
        replace_copy(a, b, hashlib.sha256(b'original').hexdigest(), 8)
    assert b.stat().st_ino == inode
    assert b.read_bytes() == b'mutation'


def test_archive_preserves_nested_files_links_empty_dirs_and_detects_drift(tmp_path, monkeypatch):
    monkeypatch.setattr(archive_v6_inputs, 'ROOT', tmp_path)
    source = tmp_path / 'history'
    source.mkdir(); (source / 'empty').mkdir()
    (source / 'data').write_bytes(b'historical\0data')
    (source / 'data').chmod(0o640)
    os.link(source / 'data', source / 'hardlink')
    (source / 'link').symlink_to('data')
    bundle = tmp_path / 'bundle'; bundle.mkdir()
    group = dict(id='sample', members=['history'], shallow=[])
    result = archive_v6_inputs.pack_one(group, bundle)
    assert result['source']['files'] == 2
    assert result['source']['directories'] == 2
    assert result['source']['symlinks'] == 1
    assert archive_v6_inputs.archive_census(bundle / 'sample.tar.zst') == {
        'files': 2, 'directories': 2, 'symlinks': 1}
    subprocess.run(['tar', '--xattrs', '--acls', '-I', 'zstd -T1 -d', '-df',
                    str(bundle / 'sample.tar.zst')], cwd=tmp_path, check=True)
    restored = tmp_path / 'restored'; restored.mkdir()
    subprocess.run(['tar', '-I', 'zstd -T1 -d', '-xf', str(bundle / 'sample.tar.zst'),
                    '-C', str(restored)], check=True)
    assert (restored / 'history/data').read_bytes() == b'historical\0data'
    assert (restored / 'history/empty').is_dir()
    assert (restored / 'history/link').is_symlink()
    (source / 'data').write_bytes(b'changed')
    assert archive_v6_inputs.fingerprint(group['members']) != result['source']
    comparison = subprocess.run(['tar', '-I', 'zstd -T1 -d', '-df',
                                 str(bundle / 'sample.tar.zst')], cwd=tmp_path, capture_output=True)
    assert comparison.returncode != 0


@pytest.mark.parametrize('failure', ['member_counts', 'archive_hash'])
def test_retirement_guards_leave_source_intact(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(archive_v6_inputs, 'ROOT', tmp_path)
    monkeypatch.setattr(archive_v6_inputs, 'check_drive', lambda _: None)
    monkeypatch.setattr(archive_v6_inputs, 'check_layout', lambda _: None)
    source = tmp_path / 'history'; source.mkdir()
    data = source / 'data'; data.write_bytes(b'irreplaceable history')
    bundle = tmp_path / 'bundle'; bundle.mkdir()
    destination = tmp_path / 'external'; destination.mkdir()
    plan = {'groups': [{'id': 'sample', 'members': ['history'], 'shallow': []}]}
    (bundle / 'plan.json').write_text(json.dumps(plan))
    completion = dict(plan_sha256=archive_v6_inputs.sha(bundle / 'plan.json'),
                      files=1, directories=1, symlinks=0)
    (destination / 'VERIFIED.json').write_text(json.dumps(completion))
    census = dict(completion)
    if failure == 'member_counts':
        census['files'] = 0
    (destination / 'MEMBERS-VERIFIED.json').write_text(json.dumps(census))
    (destination / 'sample.verified.json').write_text(json.dumps({'packed': {'sha256': '0' * 64}}))
    (destination / 'sample.tar.zst').write_bytes(b'corrupted archive')
    with pytest.raises(ValueError, match='member counts|External content drifted'):
        archive_v6_inputs.retire(bundle, destination, plan)
    assert data.read_bytes() == b'irreplaceable history'
