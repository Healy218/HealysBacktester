"""Disk-backed routing over immutable bounded packs; no all-capture RAM index."""
from collections import OrderedDict
import json
from pathlib import Path
import sqlite3

from nn_meta.v7.execution import CaptureUnavailable, QuotePolicy
from nn_meta.v7.quote_archive import QuoteArchive
from nn_meta.v7.packed_quotes import PackedQuoteArchive as V1, FORMAT as FORMAT1
from nn_meta.v7.packed_quotes_v2 import PackedQuoteArchive as V2, FORMAT as FORMAT2
from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
from options.data.massive_ticks import integer_ns


def write_index(destination, packs, *, binding):
    """Seal exact coverage routing. Requests remain in their frozen demand stores."""
    count=0
    with transaction(destination) as temp:
        with sqlite3.connect(temp/'index.sqlite3') as db:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('CREATE TABLE packs (id INTEGER PRIMARY KEY,path TEXT UNIQUE NOT NULL,receipt_sha256 TEXT NOT NULL,format TEXT NOT NULL)')
            db.execute('CREATE TABLE ranges (contract TEXT NOT NULL,kind TEXT NOT NULL,start_ns INTEGER NOT NULL,end_ns INTEGER NOT NULL,pack INTEGER NOT NULL,capture_id TEXT UNIQUE NOT NULL)')
            db.execute('CREATE INDEX windows ON ranges(contract,kind,start_ns,end_ns)')
            for number,path in enumerate(packs):
                path=Path(path).resolve()
                doc=verify(path)
                reader={FORMAT1:V1,FORMAT2:V2}.get(doc.get('format'))
                if reader is None:raise ValueError('Unsupported pack format')
                digest=sha(path/'complete.json')
                db.execute('INSERT INTO packs VALUES (?,?,?,?)',(number,str(path),digest,doc['format']))
                with reader(path,cache_shards=1) as archive:
                    for cid,contract,kind,start,end in archive.db.execute('SELECT capture_id,contract,kind,start_ns,end_ns FROM captures'):
                        if db.execute('SELECT 1 FROM ranges WHERE contract=? AND kind=? AND start_ns<? AND end_ns>?',
                            (contract,kind,end,start)).fetchone():
                            raise ValueError('Overlapping indexed captures require reconciliation')
                        if cid!=identity(dict(contract=contract,kind=kind,start_ns=start,end_ns=end)):
                            raise ValueError('Indexed capture identity drift')
                        db.execute('INSERT INTO ranges VALUES (?,?,?,?,?,?)',(contract,kind,start,end,number,cid))
                        count+=1
                if sha(path/'complete.json')!=digest:raise ValueError('Pack changed during index publication')
        if not count:raise ValueError('No completed captures to index')
        (temp/'binding.json').write_text(json.dumps(binding,sort_keys=True)+'\n')
        receipt(temp,dict(identity=identity(binding),format='v7-packed-quote-index-v1',captures=count,
                          full_execution_coverage=False))
    return verify(destination,expected_identity=identity(binding))


class IndexedQuoteArchive(QuoteArchive):
    def __init__(self, root, *, cache_packs=2, policy=QuotePolicy()):
        self.root=Path(root).resolve()
        doc=verify(self.root)
        if doc.get('format')!='v7-packed-quote-index-v1':raise ValueError('Sealed packed routing index required')
        if type(cache_packs) is not int or cache_packs<1:raise ValueError('Positive pack cache bound required')
        self.cache_packs,self.policy=cache_packs,policy
        self.cache=OrderedDict()
        self.db=sqlite3.connect((self.root/'index.sqlite3').as_uri()+'?mode=ro&immutable=1',uri=True)
        if self.db.execute('SELECT COUNT(*) FROM ranges').fetchone()[0]!=doc['captures']:
            self.close();raise ValueError('Index capture census drift')

    def close(self):
        for reader in self.cache.values():reader.close()
        self.cache.clear();self.db.close()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()

    def _pack(self,number):
        if number not in self.cache:
            row=self.db.execute('SELECT path,receipt_sha256,format FROM packs WHERE id=?',(number,)).fetchone()
            if row is None:raise ValueError('Capture references absent pack')
            path,digest,format=row
            if sha(Path(path)/'complete.json')!=digest:raise ValueError('Indexed pack receipt drift')
            cls={FORMAT1:V1,FORMAT2:V2}.get(format)
            if cls is None:raise ValueError('Unsupported indexed format')
            self.cache[number]=cls(path,cache_shards=1,policy=self.policy)
            while len(self.cache)>self.cache_packs:self.cache.popitem(last=False)[1].close()
        self.cache.move_to_end(number)
        return self.cache[number]

    def window(self,contract,kind,start_ns,end_ns):
        start_ns,end_ns=integer_ns(start_ns),integer_ns(end_ns)
        if not start_ns<end_ns or end_ns-start_ns>86400*10**9 or kind not in ('quotes','trades'):
            raise ValueError('A bounded positive capture window is required')
        contract=contract.removeprefix('O:')
        cursor,rows,sources=start_ns,[],[]
        for start,end,number,cid in self.db.execute('SELECT start_ns,end_ns,pack,capture_id FROM ranges WHERE '
            'contract=? AND kind=? AND start_ns<? AND end_ns>? ORDER BY start_ns',(contract,kind,end_ns,start_ns)):
            if start>cursor:raise CaptureUnavailable('Gap in indexed capture interval')
            data,manifest=self._pack(number).window(contract,kind,max(start,start_ns),min(end,end_ns))
            if [s['capture_id'] for s in manifest['derived_from_captures']]!=[cid]:
                raise ValueError('Index range and packed coverage differ')
            rows.extend(data);sources.extend(manifest['derived_from_captures'])
            cursor=min(end,end_ns)
        if cursor!=end_ns:raise CaptureUnavailable('Indexed capture does not reach required window end')
        return rows,dict(schema='massive-option-ticks-v1',provider='massive',contract='O:'+contract,
            kind=kind,start_ns=start_ns,end_ns=end_ns,complete=True,records=len(rows),
            records_sha256=identity(rows),derived_from_captures=sources)
