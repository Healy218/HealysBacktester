import sqlite3

import pytest

from nn_meta.v7.storage import receipt,sha
from scripts.compact_v7_execution_scratch import compact


def test_only_equivalent_scratch_is_removed_and_sealed_copy_unchanged(tmp_path):
    source=tmp_path/'working'/'sid';source.mkdir(parents=True)
    target=tmp_path/'jobs'/'sid';target.mkdir(parents=True)
    with sqlite3.connect(source/'jobs.sqlite3') as a:
        a.execute('CREATE TABLE numbers(n)');a.execute('INSERT INTO numbers VALUES(1)');a.commit()
        with sqlite3.connect(target/'jobs.sqlite3') as b:a.backup(b)
    receipt(target,{'identity':'fixture'});before=sha(target/'jobs.sqlite3')
    assert compact(tmp_path)>0
    assert not (source/'jobs.sqlite3').exists() and sha(target/'jobs.sqlite3')==before
    assert compact(tmp_path)==0


def test_different_scratch_is_retained(tmp_path):
    for name,value in [('working',1),('jobs',2)]:
        path=tmp_path/name/'sid';path.mkdir(parents=True)
        with sqlite3.connect(path/'jobs.sqlite3') as db:
            db.execute('CREATE TABLE numbers(n)');db.execute('INSERT INTO numbers VALUES(?)',(value,))
    receipt(tmp_path/'jobs'/'sid',{'identity':'fixture'})
    with pytest.raises(ValueError,match='equivalent'):compact(tmp_path)
    assert (tmp_path/'working'/'sid'/'jobs.sqlite3').exists()
