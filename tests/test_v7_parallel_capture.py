import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from nn_meta.v7.storage import identity, verify
from options.data.massive_ticks import MassiveTicks, TickDataError
from scripts import v7_parallel_capture as parallel
from scripts.run_v7_capture_campaign import acquire as old_acquire
from scripts.run_v7_capture_campaign_v2 import acquire, pack_binding, reuse


def items(n=8):
    result=[]
    for i in range(n):
        item=dict(contract='SPY220318C00420000',kind='quotes',start_ns=i*100+1,end_ns=i*100+100)
        result.append(dict(item,capture_id=identity(item)))
    return result


def capture(self,contract,kind,start_ns,end_ns,**kwargs):
    rows=[dict(sip_timestamp=start_ns,bid_price=1.,ask_price=1.1,bid_size=1,ask_size=1)]
    return rows,dict(schema='massive-option-ticks-v1',provider='massive',contract='O:'+contract,kind=kind,
        start_ns=start_ns,end_ns=end_ns,complete=True,records=len(rows),records_sha256=identity(rows))


@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setenv('MASSIVE_API_KEY','fixture')
    monkeypatch.setattr(MassiveTicks,'capture',capture)
    budget=tmp_path/'data';budget.mkdir()
    (budget/'quota.json').write_text(json.dumps(dict(limit_bytes=10*1024**3,used_bytes=0,reservations={})))
    with ThreadPoolExecutor(max_workers=4) as pool:
        monkeypatch.setattr(parallel,'_POOL',pool)
        yield budget,tmp_path/'attempts'


def test_parallel_download_roundtrip_and_restart_without_charge(setup):
    from nn_meta.v7.packed_quotes_v2 import PackedQuoteArchive
    budget,attempts=setup;requested=items()
    job=({},requested,str(budget/'pack'),str(budget),'fixture',{},str(attempts),dict(sources={}),4)
    assert acquire(job)['status']=='completed'
    quota=(budget/'quota.json').read_bytes()
    assert acquire(job)['status']=='reused'
    assert quota==(budget/'quota.json').read_bytes()
    with PackedQuoteArchive(budget/'pack') as archive:
        for item in requested:
            rows,manifest=archive.window(*[item[k] for k in ('contract','kind','start_ns','end_ns')])
            assert rows==capture(None,**{k:item[k] for k in ('contract','kind','start_ns','end_ns')})[0]
            assert manifest['complete']
    assert not json.loads(quota)['reservations']


def test_original_pack_is_reused_without_relabeling(setup):
    budget,attempts=setup;requested=items(1)
    old=({},requested,str(budget/'pack'),str(budget),'fixture',{},str(attempts))
    assert old_acquire(old)['status']=='completed'
    original=(budget/'pack/binding.json').read_bytes();quota=(budget/'quota.json').read_bytes()
    assert acquire((*old,dict(sources={}),4))['status']=='reused'
    assert original==(budget/'pack/binding.json').read_bytes()
    assert quota==(budget/'quota.json').read_bytes()
    wrong=pack_binding({},items(2),'fixture',{})
    with pytest.raises(ValueError,match='Retained pack'):
        reuse(budget/'pack',wrong,dict(sources={}))


def test_concurrency_is_bounded_and_failure_drains(setup,monkeypatch):
    budget,attempts=setup;lock=threading.Lock();active=peak=0
    def delayed(self,**kwargs):
        nonlocal active,peak
        with lock:active+=1;peak=max(peak,active)
        try:
            time.sleep(.03)
            if kwargs['start_ns']==201:raise TickDataError('Massive ticks HTTP 403')
            return capture(self,**kwargs)
        finally:
            with lock:active-=1
    monkeypatch.setattr(MassiveTicks,'capture',delayed)
    job=({},items(),str(budget/'failed'),str(budget),'fixture',{},str(attempts),dict(sources={}),4)
    report=acquire(job)
    assert report['status']=='failed' and report['error']['reason']=='Massive ticks HTTP 403'
    assert 1<peak<=4 and active==0
    assert not (budget/'failed').exists()
    assert not json.loads((budget/'quota.json').read_text())['reservations']


def test_dense_windows_split_without_gaps_or_tick_loss(setup,monkeypatch):
    from nn_meta.v7.packed_quotes_v2 import PackedQuoteArchive
    budget,attempts=setup
    def dense(self,**kwargs):
        assert kwargs['page_size']==5000 and kwargs['max_pages']==4
        if kwargs['end_ns']-kwargs['start_ns']>25:
            raise TickDataError('page budget exhausted; capture incomplete')
        return capture(self,**kwargs)
    monkeypatch.setattr(MassiveTicks,'capture',dense)
    requested=items(4)
    job=({},requested,str(budget/'pack'),str(budget),'fixture',{},str(attempts),dict(sources={}),4)
    report=acquire(job)
    assert report['status']=='completed' and len(report['split_attempts'])==12
    assert verify(budget/'pack')['captures']==16
    with PackedQuoteArchive(budget/'pack') as archive:
        for item in requested:
            rows,manifest=archive.window(*[item[k] for k in ('contract','kind','start_ns','end_ns')])
            assert len(rows)==4 and len(manifest['derived_from_captures'])==4


def test_writer_failure_closes_pending_streams(setup,monkeypatch):
    import nn_meta.v7.packed_quotes_v2 as packed
    budget,attempts=setup
    def reject(*args):raise ValueError('fixture encoding failure')
    monkeypatch.setattr(packed,'encode',reject)
    job=({},items(),str(budget/'failed'),str(budget),'fixture',{},str(attempts),dict(sources={}),4)
    assert acquire(job)['status']=='failed'
    assert not json.loads((budget/'quota.json').read_text())['reservations']


def test_tampered_pack_rejected(setup):
    budget,attempts=setup;requested=items(1)
    job=({},requested,str(budget/'pack'),str(budget),'fixture',{},str(attempts),dict(sources={}),4)
    acquire(job)
    with (budget/'pack/captures.sqlite3').open('ab') as f:f.write(b'changed')
    with pytest.raises(ValueError):acquire(job)
