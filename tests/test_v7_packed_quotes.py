import hashlib
import json
import sqlite3

import pytest

from nn_meta.v7.execution import CaptureUnavailable
from nn_meta.v7.packed_quotes import PackedQuoteArchive, write_pack, encode, decode
from nn_meta.v7.storage import identity
from scripts.plan_v7_joined_sample import summarize
from scripts.capture_v7_joined_sample import capture_split
from options.data.massive_ticks import canonical_bytes, TickDataError

CONTRACT='SPY220316P00420000'


def entry(start=0,end=10,rows=None):
    scope=dict(contract=CONTRACT,kind='quotes',start_ns=start,end_ns=end)
    item=dict(scope,capture_id=identity(scope))
    if rows is None:
        rows=[dict(sip_timestamp=start,bid_price=1.125,ask_price=1.25,bid_size=1,ask_size=1)]
    manifest=dict(scope,contract='O:'+CONTRACT,schema='massive-option-ticks-v1',provider='massive',
                  complete=True,records=len(rows),records_sha256=identity(rows))
    return item,rows,manifest


def test_packed_lossless_nested_missing_null_duplicates_large_ns():
    start=1647351270000000001
    rows=[dict(sip_timestamp=start,size=2,price=1.125,conditions=[])]*2
    rows += [dict(sip_timestamp=start+1,size=None,price=-0.0,nested={'a':[1,True,None]})]
    item,rows,manifest=entry(start,start+10,rows)
    blob,size,digest=encode(item,rows,manifest)
    restored,meta=decode(item,blob,size,digest)
    assert canonical_bytes(restored)==canonical_bytes(rows)
    assert meta==manifest
    with pytest.raises(ValueError,match='hash'):
        decode(item,blob+b'x',size,digest)
    with pytest.raises(ValueError,match='byte limit'):
        decode(item,blob,2**40,digest)


def test_packed_adjacent_windows_empty_gaps_and_cache_detachment(tmp_path):
    root=tmp_path/'pack'
    entries=[entry(0,10),entry(10,20,[]),entry(20,30)]
    write_pack(root,entries,binding={'test':1})
    with PackedQuoteArchive(root,cache_shards=1) as archive:
        rows,manifest=archive.window(CONTRACT,'quotes',0,30)
        assert [r['sip_timestamp'] for r in rows]==[0,20]
        rows[1]['bid_price']=500
        assert archive.window(CONTRACT,'quotes',20,30)[0][0]['bid_price']==1.125
        assert archive.window(CONTRACT,'quotes',10,20)[0]==[]
        assert manifest['records_sha256']==identity([entries[0][1][0],entries[2][1][0]])
        for kind,start,end in [('quotes',0,31),('trades',0,30)]:
            with pytest.raises(CaptureUnavailable):
                archive.window(CONTRACT,kind,start,end)
    with pytest.raises(FileExistsError):
        write_pack(root,entries,binding={'test':1})


def test_packed_overlap_and_interruption_never_publish_receipt(tmp_path):
    root=tmp_path/'pack'
    with pytest.raises(ValueError,match='Overlapping'):
        write_pack(root,[entry(0,10),entry(9,20)],binding={})
    assert not root.exists()
    assert list(tmp_path.glob('pack.partial-*'))
    assert not list(tmp_path.glob('pack.partial-*/complete.json'))


def test_pack_tampering_fails_before_use(tmp_path):
    root=tmp_path/'pack'
    write_pack(root,[entry()],binding={})
    with sqlite3.connect(root/'captures.sqlite3') as db:
        db.execute("UPDATE captures SET payload=?",(b'wrong',))
    with pytest.raises(ValueError,match='integrity'):
        PackedQuoteArchive(root)


def test_joined_sample_counts_exact_ranges_and_retains_gaps():
    start=1647351600*10**9
    data=[]
    for kind in ('quotes','trades'):
        for lo,hi in ((start,start+900*10**9),(start+900*10**9,start+1000*10**9),
                      (start+1001*10**9,start+1002*10**9)):
            scope=dict(contract=CONTRACT,kind=kind,start_ns=lo,end_ns=hi)
            data.append((identity(scope),CONTRACT,'2022-03-15',kind,lo,hi))
    result=summarize(data,security_id='security',quartile=0,maximum=12)
    assert sum(result['population'].values())==2
    assert sum(result['seconds_ns'].values())==1001*10**9


def test_dense_capture_splits_exactly_and_preserves_failure():
    class Client:
        def capture(self,**kwargs):
            if kwargs['end_ns']-kwargs['start_ns']>5:
                raise TickDataError('page budget exhausted; capture incomplete')
            _,rows,manifest=entry(kwargs['start_ns'],kwargs['end_ns'])
            return rows,manifest
    failures=[]
    result=list(capture_split(Client(),entry()[0],failures))
    assert [(e[0]['start_ns'],e[0]['end_ns']) for e in result]==[(0,5),(5,10)]
    assert len(failures)==1
    assert all(e[0]['capture_id']==identity({k:e[0][k] for k in ('contract','kind','start_ns','end_ns')}) for e in result)
