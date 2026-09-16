import json
from pathlib import Path
from types import SimpleNamespace
import pytest

from nn_meta.v7.storage import verify
from scripts.capture_v7_news import capture
from scripts.download_v7_data import quota_update, TASK_RESERVATION


def test_news_capture_binds_exclusive_end_and_preserves_empty_evidence(tmp_path, monkeypatch):
    import scripts.download_v7_data as downloader
    monkeypatch.setattr(downloader, 'disk_guard', lambda *a: None)
    monkeypatch.setattr('scripts.capture_v7_news.time.sleep', lambda *a: None)
    quota_update(tmp_path, initialize=2*TASK_RESERVATION)
    calls = []
    def get(session, url, params):
        calls.append(dict(params))
        body = {'news': [], 'next_page_token': None}
        return json.dumps(body).encode(), body
    monkeypatch.setattr(downloader, 'get_json', get)
    args = SimpleNamespace(symbols='VERU', start='2022-11-09', end='2022-11-11',
                           output=tmp_path/'capture', budget_root=tmp_path)
    result = capture(args)
    assert result['articles'] == 0 and not result['research_ready']
    assert calls[0]['end'] == '2022-11-10T23:59:59.999999999Z'
    assert verify(args.output)['query']['params'] == calls[0]
    assert capture(args)['status'] == 'reused' and len(calls) == 1
    assert not json.loads((tmp_path/'quota.json').read_text())['reservations']


def test_failed_news_retries_charge_only_new_partial_bytes(tmp_path, monkeypatch):
    import scripts.download_v7_data as downloader
    monkeypatch.setattr(downloader, 'disk_guard', lambda *a: None)
    monkeypatch.setattr('scripts.capture_v7_news.time.sleep', lambda *a: None)
    quota_update(tmp_path, initialize=2*TASK_RESERVATION)
    def get(session, url, params):
        body = {'news': [{'id': 1}], 'next_page_token': 'repeated'}
        return json.dumps(body).encode(), body
    monkeypatch.setattr(downloader, 'get_json', get)
    args = SimpleNamespace(symbols='VERU', start='2022-11-09', end='2022-11-11',
                           output=tmp_path/'capture', budget_root=tmp_path)
    used = []
    initial = json.loads((tmp_path/'quota.json').read_text())['used_bytes']
    for _ in range(2):
        with pytest.raises(ValueError, match='Duplicate news ID'):
            capture(args)
        doc = json.loads((tmp_path/'quota.json').read_text())
        used.append(doc['used_bytes']-initial)
        assert not doc['reservations'] and not args.output.exists()
    assert used[1] == 2*used[0]
