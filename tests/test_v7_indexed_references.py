import json
import sqlite3

import pytest

from nn_meta.v7.indexed_references import IndexedContractReferences,ReferenceAdmissionPending
from nn_meta.v7.packed_references import write_pack,query,PackedContractReferences
from nn_meta.v7.storage import receipt,sha

C='AAPL260918C00200000';D='2026-09-14'


def make_audit(tmp_path,status=200,**terms):
    row=dict(ticker='O:'+C,underlying_ticker='AAPL',expiration_date='2026-09-18',
             contract_type='call',strike_price=200,shares_per_contract=100,
             exercise_style='american',primary_exchange='XNAS')
    row.update(terms)
    pack=tmp_path/'pack'
    write_pack(pack,[(C,D,status,json.dumps(dict(status='OK',results=row)).encode(),dict(query=query(C,D)))],dict(requests=1))
    with sqlite3.connect(pack/'references.sqlite3') as db:
        admission,anchor=db.execute('SELECT admission,receipt_sha256 FROM responses').fetchone()
    audit=tmp_path/'audit';audit.mkdir()
    with sqlite3.connect(audit/'coverage.sqlite3') as db:
        db.execute('CREATE TABLE observed(security_id,contract,date,admission,pack,receipt_sha256,PRIMARY KEY(security_id,contract,date)) WITHOUT ROWID')
        db.execute('INSERT INTO observed VALUES(?,?,?,?,?,?)',('sid',C,D,admission,str(pack),anchor))
    (audit/'report.json').write_text(json.dumps(dict(full_planned_reference_capture=True)))
    (audit/'binding.json').write_text(json.dumps(dict(inputs={str(pack/'complete.json'):sha(pack/'complete.json')})))
    receipt(audit,{'identity':'audit'})
    return audit,pack


def test_bounded_disk_router_matches_original_and_preserves_absence(tmp_path):
    audit,pack=make_audit(tmp_path)
    old=PackedContractReferences([pack])
    with IndexedContractReferences(audit,security_id='sid',cache_packs=1) as new:
        assert new.standard(C,D)==old.standard(C,D)
        assert len(new.cache)==1
        assert new.disposition(C,'2026-09-15')=='uncaptured'
        with pytest.raises(FileNotFoundError):new.standard(C,'2026-09-15')
    old.close()
    with IndexedContractReferences(audit,security_id='other') as new:
        with pytest.raises(FileNotFoundError):new.standard(C,D)


@pytest.mark.parametrize('status,terms',[(404,{}),(200,{'additional_underlyings':[{'underlying':'USD','amount':1}]})])
def test_known_failures_are_explicit_frontier_blocks_not_terms(tmp_path,status,terms):
    audit,pack=make_audit(tmp_path,status,**terms)
    with IndexedContractReferences(audit,security_id='sid') as new:
        with pytest.raises(ReferenceAdmissionPending):new.standard(C,D)


def test_pack_tampering_is_integrity_failure_not_recoverable_gap(tmp_path):
    audit,pack=make_audit(tmp_path)
    with IndexedContractReferences(audit,security_id='sid') as new:
        with sqlite3.connect(pack/'references.sqlite3') as db:db.execute('UPDATE responses SET body=?',(b'{}',))
        with pytest.raises(ValueError,match='integrity'):new.standard(C,D)
