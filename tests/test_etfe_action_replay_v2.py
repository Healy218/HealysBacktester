import json
import pandas as pd
import pytest
from nn_meta.etfe import action_replay_v2 as ar
from tests.test_etfe_action_replay import event,raw,receipt,JOB,Fake,response


def test_cursor_rounds_down_without_losing_subsecond_events():
    assert pd.Timestamp(ar.overlap_cursor('2026-09-17T09:30:08.378721Z'))==pd.Timestamp('2026-09-17T09:30:08Z')
    events,_,_,_=ar.parse_page(raw([event(at='2026-09-17T09:30:08.378324Z')]),receipt(since=ar.overlap_cursor('2026-09-17T09:30:08.378721Z')),JOB)
    assert len(events)==1
    with pytest.raises(ValueError):ar.parse_page(raw([event(at='2026-09-17T09:30:07.999Z')]),receipt(since='2026-09-17T09:30:08Z'),JOB)


def test_second_overlap_preserves_every_occurrence(tmp_path,monkeypatch):
    plan=dict(sha256='a'*64,jobs=[JOB],type_filter='cash_dividend_corporateaction_event',limits=dict(max_requests=96,max_seconds=900,max_page_bytes=4096,max_root_bytes=2**20,max_day_bytes=2**19,max_total_bytes=2**20))
    monkeypatch.setattr(ar,'verify',lambda _:plan)
    a=event('a','2026-09-17T09:30:08.378324Z');b=event('b','2026-09-17T09:30:08.378721Z');c=event('c','2026-09-17T09:30:08.999999Z')
    http=Fake([response([a,b],'byte_limit'),response([a,b,c])])
    result=ar.run(tmp_path,http,sleep=lambda _:None,resource_guard=lambda *_:None)
    assert result['transport_complete'] and pd.Timestamp(http.calls[1]['since'])==pd.Timestamp('2026-09-17T09:30:08Z')
    pages,_,_,_=ar.committed(tmp_path,JOB,plan)
    assert sum(len(p['events']) for p in pages)==5 and sum(p['new_events'] for p in pages)==3
