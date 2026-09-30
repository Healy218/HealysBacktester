import json
from pathlib import Path
import sqlite3

import pytest

from scripts.migrate_v7_payloads_mrha import digest, relocate, stamp


def test_sqlite_reader_open_before_move_and_new_reader_both_work(tmp_path):
    src = tmp_path / 'local' / 'captures.sqlite3'
    src.parent.mkdir()
    with sqlite3.connect(src) as db:
        db.execute('CREATE TABLE evidence(value TEXT)')
        db.execute('INSERT INTO evidence VALUES("preserved")')
    expected = digest(src)
    existing = sqlite3.connect(src.as_uri() + '?mode=ro&immutable=1', uri=True)
    dst = tmp_path / 'external' / expected
    assert relocate(src, dst, expected, stamp(src)) == 'moved'
    assert src.is_symlink() and digest(src) == expected
    assert existing.execute('SELECT value FROM evidence').fetchone() == ('preserved',)
    with sqlite3.connect(src.resolve().as_uri() + '?mode=ro&immutable=1', uri=True) as later:
        assert later.execute('SELECT value FROM evidence').fetchone() == ('preserved',)
    existing.close()
    assert relocate(src, dst, expected, []) == 'resumed_link'


def test_failure_before_cutover_keeps_original_and_reuses_verified_copy(tmp_path):
    src = tmp_path / 'data'; src.write_bytes(b'evidence')
    expected = digest(src); original = stamp(src); dst = tmp_path / 'external' / expected
    def fail():
        raise RuntimeError('simulated interruption')
    with pytest.raises(RuntimeError):
        relocate(src, dst, expected, original, pre_replace=fail)
    assert not src.is_symlink() and src.read_bytes() == b'evidence'
    assert dst.read_bytes() == b'evidence'
    relocate(src, dst, expected, original)
    assert src.is_symlink()


def test_bad_source_or_destination_never_retires_original(tmp_path):
    src = tmp_path / 'data'; src.write_bytes(b'original')
    expected = digest(src); original = stamp(src); dst = tmp_path / 'external'
    dst.write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='external payload'):
        relocate(src, dst, expected, original)
    assert not src.is_symlink()
    dst.unlink(); src.write_bytes(b'changed')
    with pytest.raises(ValueError, match='Source metadata'):
        relocate(src, dst, expected, original)
    assert not src.is_symlink()


def test_receipt_checksum_blocks_even_metadata_stable_wrong_bytes(tmp_path):
    src = tmp_path / 'data'; src.write_bytes(b'wrong')
    with pytest.raises(ValueError, match='sealed receipt'):
        relocate(src, tmp_path / 'external', 'a' * 64, stamp(src))
    assert src.read_bytes() == b'wrong' and not src.is_symlink()


def test_identical_sources_share_external_content_without_changing_headers(tmp_path):
    header = tmp_path / 'complete.json'; header.write_text(json.dumps({'complete': True}))
    before = header.read_bytes(); dst = tmp_path / 'external' / 'object'
    for name in ['first', 'second']:
        src = tmp_path / name; src.write_bytes(b'same immutable payload')
        relocate(src, dst, digest(src), stamp(src))
    assert (tmp_path / 'first').resolve() == (tmp_path / 'second').resolve()
    assert len(list(dst.parent.iterdir())) == 1 and header.read_bytes() == before
