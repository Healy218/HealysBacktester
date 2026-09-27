import errno
import hashlib
import json
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
    (source / 'link').symlink_to('data')
    bundle = tmp_path / 'bundle'; bundle.mkdir()
    group = dict(id='sample', members=['history'], shallow=[])
    result = archive_v6_inputs.pack_one(group, bundle)
    assert result['source']['files'] == 1
    assert result['source']['directories'] == 2
    assert result['source']['symlinks'] == 1
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
