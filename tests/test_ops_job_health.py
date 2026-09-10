from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import sys

import pandas as pd
import pytest

from scripts.job_receipts import record
from scripts.run_ops_job import run
from scripts.check_ops_health import check_job, check_capture
from scripts.verify_backup_sample import verify


def test_success_followed_by_failure_is_unhealthy(tmp_path):
    assert run('test',tmp_path,[sys.executable,'-c','print("ok")'])==0
    assert check_job(tmp_path/'test',3600,datetime.now(timezone.utc))['healthy']
    assert run('test',tmp_path,[sys.executable,'-c','raise SystemExit(2)'])==2
    assert not check_job(tmp_path/'test',3600,datetime.now(timezone.utc))['healthy']
    assert json.loads((tmp_path/'test/last-success.json').read_text())['state']=='success'


def test_timeout_and_missing_command_record_failure(tmp_path):
    assert run('timeout',tmp_path,[sys.executable,'-c','import time;time.sleep(10)'],timeout=.05)==124
    assert run('missing',tmp_path,['/no/such/program'])==127
    assert not check_job(tmp_path/'missing',3600,datetime.now(timezone.utc))['healthy']


def test_missing_stale_and_future_receipts_fail(tmp_path):
    now=datetime.now(timezone.utc)
    assert not check_job(tmp_path/'none',3600,now)['healthy']
    record(tmp_path,'job','success',returncode=0)
    assert not check_job(tmp_path/'job',3600,now+timedelta(days=2))['healthy']
    assert not check_job(tmp_path/'job',3600,now-timedelta(days=2))['healthy']
    record(tmp_path,'job','running')
    assert not check_job(tmp_path/'job',3600,datetime.now(timezone.utc))['healthy']


def test_capture_freshness_is_not_file_mtime(tmp_path):
    now=datetime(2026,9,10,tzinfo=timezone.utc)
    pd.DataFrame({'ts_utc':['2026-09-01T00:00Z']}).to_parquet(tmp_path/'2026-09.parquet')
    assert not check_capture(tmp_path,3600,now)['healthy']
    pd.DataFrame({'ts_utc':['2026-09-10T00:00Z']}).to_parquet(tmp_path/'2026-09.parquet')
    assert check_capture(tmp_path,3600,now)['healthy']
    pd.DataFrame({'ts_utc':['2026-09-11T00:00Z']}).to_parquet(tmp_path/'2026-09.parquet')
    assert not check_capture(tmp_path,3600,now)['healthy']


def test_restore_sample_matches_and_preserves_original(tmp_path,monkeypatch):
    source=tmp_path/'data';source.write_bytes(b'irreplaceable')
    def cp(command,**kw):Path(command[-1]).write_bytes(source.read_bytes())
    monkeypatch.setattr('scripts.verify_backup_sample.subprocess.run',cp)
    assert verify(source,'gs://bucket/data',gsutil='gsutil',state_dir=tmp_path/'state')['state']=='success'
    assert source.read_bytes()==b'irreplaceable'
    def bad(command,**kw):Path(command[-1]).write_bytes(b'wrong')
    monkeypatch.setattr('scripts.verify_backup_sample.subprocess.run',bad)
    with pytest.raises(ValueError,match='differ'):verify(source,'gs://bucket/data',gsutil='gsutil',state_dir=tmp_path/'state')
    assert not check_job(tmp_path/'state/backup-restore',3600,datetime.now(timezone.utc))['healthy']


def test_collectors_have_independent_receipts(tmp_path,monkeypatch):
    from fa import collect
    from types import SimpleNamespace
    monkeypatch.setattr(collect,'STATE',tmp_path)
    def fail():raise RuntimeError('secret message not stored')
    monkeypatch.setattr(collect,'COLLECTORS',[('good',SimpleNamespace(collect=lambda:0)),('bad',SimpleNamespace(collect=fail))])
    monkeypatch.setenv('FA_SKIP_COLLECTORS','')
    assert collect.main()==0
    assert check_job(tmp_path/'collector-good',3600,datetime.now(timezone.utc))['healthy']
    assert not check_job(tmp_path/'collector-bad',3600,datetime.now(timezone.utc))['healthy']
    assert 'secret message' not in (tmp_path/'collector-bad/latest.json').read_text()


def test_overlapping_run_does_not_replace_active_receipt(tmp_path):
    import fcntl
    folder=tmp_path/'job';folder.mkdir()
    record(tmp_path,'job','running')
    before=(folder/'latest.json').read_bytes()
    with (folder/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        assert run('job',tmp_path,[sys.executable,'-c','raise Exception()'])==75
    assert (folder/'latest.json').read_bytes()==before


def test_bad_or_empty_capture_partition_is_unhealthy(tmp_path):
    (tmp_path/'2026-09.parquet').write_bytes(b'not parquet')
    assert not check_capture(tmp_path,3600,datetime.now(timezone.utc))['healthy']


def test_timeout_kills_descendants_even_if_parent_exits_on_term(tmp_path):
    import time
    marker=tmp_path/'orphan-wrote'
    child="import signal,time,pathlib;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(.6);pathlib.Path("+repr(str(marker))+").write_text('bad')"
    parent="import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',"+repr(child)+"]);time.sleep(10)"
    assert run('tree',tmp_path,[sys.executable,'-c',parent],timeout=.2)==124
    time.sleep(.65)
    assert not marker.exists()
