import pytest
from nn_meta.v7.execution import CaptureUnavailable
from nn_meta.v7.packed_quotes_v2 import write_pack
from nn_meta.v7.packed_quote_index import write_index, IndexedQuoteArchive
from tests.test_v7_packed_quotes import entry, CONTRACT


def test_index_routes_across_packs_with_bounded_cache_and_gaps(tmp_path):
    packs=[]
    for index,(start,end) in enumerate([(0,10),(10,20),(30,40)]):
        root=tmp_path/str(index)
        write_pack(root,[entry(start,end)],binding={'i':index})
        packs.append(root)
    index=tmp_path/'index'
    write_index(index,packs,binding={'complete_scope':False})
    with IndexedQuoteArchive(index,cache_packs=1) as archive:
        rows,manifest=archive.window(CONTRACT,'quotes',5,20)
        assert [r['sip_timestamp'] for r in rows]==[10]
        assert len(manifest['derived_from_captures'])==2
        assert len(archive.cache)==1
        with pytest.raises(CaptureUnavailable):archive.window(CONTRACT,'quotes',5,35)
    (packs[0]/'complete.json').write_text('{}')
    with IndexedQuoteArchive(index) as archive:
        with pytest.raises(ValueError,match='receipt drift'):
            archive.window(CONTRACT,'quotes',0,10)


def test_index_rejects_overlap_without_publishing(tmp_path):
    for name,start in [('a',0),('b',5)]:
        write_pack(tmp_path/name,[entry(start,10)],binding={})
    with pytest.raises(ValueError,match='Overlapping'):
        write_index(tmp_path/'index',[tmp_path/'a',tmp_path/'b'],binding={})
    assert not (tmp_path/'index').exists()
