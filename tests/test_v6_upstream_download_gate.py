import json

import pytest

from scripts.check_v7_entry_complete import complete


@pytest.mark.parametrize('change', [
    {'status': 'running'}, {'status': 'paused'}, {'stop_reason': 'disk_reserve_guard'},
    {'full_entry_coverage': False}, {'pending': 1}, {'campaign_identity': 'other'},
])
def test_interrupted_or_other_download_cannot_release_research(tmp_path, change):
    receipt = dict(campaign_identity='selected', status='entry_capture_complete',
                   full_entry_coverage=True, pending=0, stop_reason=None)
    path = tmp_path / 'progress.json'
    path.write_text(json.dumps(receipt))
    assert complete(path, 'selected')
    path.write_text(json.dumps(receipt | change))
    assert not complete(path, 'selected')


def test_missing_or_invalid_receipt_keeps_research_waiting(tmp_path):
    path = tmp_path / 'progress.json'
    assert not complete(path, 'selected')
    for text in ['{', 'null', '{}']:
        path.write_text(text)
        assert not complete(path, 'selected')
