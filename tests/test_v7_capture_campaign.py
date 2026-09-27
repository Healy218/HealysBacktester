import json
import sqlite3
from scripts.run_v7_capture_campaign import missing_ranges,acquire
from nn_meta.v7.storage import identity


def test_existing_union_is_subtracted_without_adding_gaps():
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE ranges(contract,kind,start_ns,end_ns)')
        db.executemany('INSERT INTO ranges VALUES(?,?,?,?)',[('C','quotes',10,20),('C','quotes',20,30),('C','quotes',40,50)])
        assert list(missing_ranges(db,'C','quotes',5,45))==[(5,10),(30,40)]
        assert list(missing_ranges(db,'C','trades',5,45))==[(5,45)]


def test_real_pack_publication_reuses_without_second_download_or_charge(tmp_path,monkeypatch):
    from options.data.massive_ticks import MassiveTicks
    from nn_meta.v7.packed_quotes_v2 import PackedQuoteArchive
    calls=[]
    def capture(self,contract,kind,start_ns,end_ns,**kwargs):
        calls.append(contract);rows=[dict(sip_timestamp=start_ns,bid_price=1.,ask_price=1.1,bid_size=1,ask_size=1)]
        return rows,dict(schema='massive-option-ticks-v1',provider='massive',contract='O:'+contract,kind=kind,
            start_ns=start_ns,end_ns=end_ns,complete=True,records=len(rows),records_sha256=identity(rows))
    monkeypatch.setenv('MASSIVE_API_KEY','fixture');monkeypatch.setattr(MassiveTicks,'capture',capture)
    budget=tmp_path/'data';budget.mkdir();(budget/'quota.json').write_text(json.dumps(dict(limit_bytes=10*1024**3,used_bytes=0,reservations={})))
    item=dict(contract='SPY220318C00420000',kind='quotes',start_ns=1,end_ns=10);item['capture_id']=identity(item)
    dest=budget/'pack';job=({},[item],str(dest),str(budget),'fixture',{},str(tmp_path/'attempts'))
    first=acquire(job);quota=json.loads((budget/'quota.json').read_text())
    second=acquire(job)
    assert first['status']=='completed' and second['status']=='reused' and len(calls)==1
    assert json.loads((budget/'quota.json').read_text())==quota and not quota['reservations']
    with PackedQuoteArchive(dest) as archive:assert archive.window(item['contract'],'quotes',1,10)[0][0]['bid_price']==1.
