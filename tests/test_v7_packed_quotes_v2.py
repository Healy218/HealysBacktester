import json
import math

import pytest

from nn_meta.v7.packed_quotes_v2 import columns, records, write_pack, PackedQuoteArchive, encode, decode
from options.data.massive_ticks import canonical_bytes
from tests.test_v7_packed_quotes import entry, CONTRACT


def test_v2_exact_typed_roundtrip_and_reader(tmp_path):
    start=1647351270000000001
    rows=[dict(sip_timestamp=start, sequence_number=9, price=-0., size=1, conditions=[2]),
          dict(sip_timestamp=start, sequence_number=9, price=-0., size=1, conditions=[2]),
          dict(sip_timestamp=start+1, sequence_number=0, price=1.123456789012345, size=None),
          dict(sip_timestamp=start+2, price=None, size=-20000000000, mixed=True),
          dict(sip_timestamp=start+3, price=1e-300, mixed=1),
          dict(sip_timestamp=start+4, price=1e300, mixed=1.)]
    packed=columns(rows)
    assert {'integer-delta','float64-shuffle','json'}=={t['kind'] for t in packed['transforms']}
    assert canonical_bytes(records(json.loads(canonical_bytes(packed))))==canonical_bytes(rows)
    assert records(columns([]))==[]
    item,data,manifest=entry(start,start+10,rows)
    root=tmp_path/'v2'
    write_pack(root,[(item,data,manifest)],binding={'version':2})
    with PackedQuoteArchive(root) as archive:
        restored,_=archive.window(CONTRACT,'quotes',start,start+10)
        assert canonical_bytes(restored)==canonical_bytes(rows)
        assert math.copysign(1.,restored[0]['price'])==-1
    blob,size,digest=encode(item,data,manifest)
    with pytest.raises(ValueError,match='hash'):
        decode(item,blob+b'x',size,digest)
    with pytest.raises(FileExistsError):
        write_pack(root,[(item,data,manifest)],binding={'version':2})


def test_v2_malformed_transform_fails_closed():
    doc=columns([{'a':1.}])
    doc['values'][0]='AAAA'
    with pytest.raises(ValueError,match='shape'):
        records(doc)
    doc=columns([{'a':1}])
    doc['values'][0]=[True]
    with pytest.raises(ValueError,match='integer delta'):
        records(doc)
