"""Alpaca-only historical SIP stock quotes for funded physical delivery.

Quote timestamps are the provider's historical SIP-feed timestamps, not locally
observed arrival times. Empty complete windows are distinct from missing capture.
"""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import json
import math
import os
from pathlib import Path
import re

import numpy as np
import pandas as pd
import requests

from nn_meta.v7.execution import CaptureUnavailable, QuoteUnavailable, QuotePolicy
from nn_meta.v7.storage import identity, verify, sha
from options.data.massive_ticks import integer_ns

SIZE_CHANGE = pd.Timestamp('2025-11-03', tz='America/New_York').value
SCHEMA = 'v7-alpaca-stock-quotes-v1'


def quote_ns(row):
    if not isinstance(row, dict):
        raise ValueError('Stock quote record must be an object')
    value = row.get('t')
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z', value):
        raise ValueError('Exact UTC quote timestamp required')
    return integer_ns(pd.Timestamp(value).value)


def scope(symbol, start_ns, end_ns):
    start_ns, end_ns = integer_ns(start_ns), integer_ns(end_ns)
    if (not isinstance(symbol, str) or not re.fullmatch(r'[A-Z][A-Z0-9.]{0,14}', symbol)
            or not start_ns < end_ns or end_ns-start_ns > 900_000_000_000):
        raise ValueError('Literal stock symbol and a positive at-most-15-minute window required')
    days = [pd.Timestamp(t, unit='ns', tz='UTC').tz_convert('America/New_York').date().isoformat()
            for t in (start_ns, end_ns-1)]
    if days[0] != days[1]:
        raise ValueError('Stock quote window must remain within one dated identity session')
    return dict(symbol=symbol, start_ns=start_ns, end_ns=end_ns, feed='sip', asof='-', currency='USD')


def verify_stock_capture(rows, manifest):
    expected = scope(manifest['symbol'], manifest['start_ns'], manifest['end_ns'])
    if (manifest.get('schema') != SCHEMA or manifest.get('provider') != 'alpaca'
            or manifest.get('complete') is not True
            or any(manifest.get(k) != v for k,v in expected.items())
            or not isinstance(rows, list) or type(manifest.get('records')) is not int
            or manifest.get('records') != len(rows)
            or manifest.get('records_sha256') != identity(rows)):
        raise ValueError('Stock capture provider, scope, completeness or bytes changed')
    stamps = [quote_ns(row) for row in rows]
    if (stamps != sorted(stamps) or any(not expected['start_ns'] <= t < expected['end_ns'] for t in stamps)):
        raise ValueError('Stock quote order/bounds violated')
    return stamps


class AlpacaStockQuotes:
    def __init__(self, *, session=None, key=None, secret=None):
        self.session = session or requests.Session()
        self.key = key or os.environ.get('ALPACA_API_KEY')
        self.secret = secret or os.environ.get('ALPACA_API_SECRET')
        if not self.key or not self.secret:
            raise ValueError('Alpaca stock credentials required')

    def capture(self, symbol, start_ns, end_ns, *, max_pages=100, page_size=10000):
        query = scope(symbol, start_ns, end_ns)
        if (type(max_pages) is not int or not 1 <= max_pages <= 100
                or type(page_size) is not int or not 1 <= page_size <= 10000):
            raise ValueError('Bounded stock quote pages required')
        # Alpaca end is inclusive. Subtract one exact ns for our [start,end).
        params = {k:query[k] for k in ('feed','asof','currency')}
        params.update(symbols=symbol, start=pd.Timestamp(start_ns, unit='ns', tz='UTC').isoformat(),
            end=pd.Timestamp(end_ns-1, unit='ns', tz='UTC').isoformat(), limit=page_size, sort='asc')
        rows, hashes, tokens = [], [], set()
        for _ in range(max_pages):
            try:
                response = self.session.get('https://data.alpaca.markets/v2/stocks/quotes', params=params,
                    headers={'APCA-API-KEY-ID':self.key,'APCA-API-SECRET-KEY':self.secret},
                    timeout=45, allow_redirects=False)
            except requests.RequestException:
                raise ValueError('Alpaca stock quote transport failed') from None
            if response.status_code != 200:
                raise ValueError(f'Alpaca stock quotes HTTP {response.status_code}')
            try:
                body = response.json()
            except ValueError:
                raise ValueError('Alpaca returned invalid stock quote JSON') from None
            if not isinstance(body, dict) or not isinstance(body.get('quotes'), dict):
                raise ValueError('Explicit Alpaca quote result mapping required')
            if set(body['quotes']) - {symbol}:
                raise ValueError('Alpaca returned an unrequested symbol')
            page = body['quotes'].get(symbol, [])
            if not isinstance(page, list):
                raise ValueError('Invalid Alpaca quote page')
            hashes.append(identity(page))
            for row in page:
                t = quote_ns(row)
                if not start_ns <= t < end_ns or (rows and t < quote_ns(rows[-1])):
                    raise ValueError('Alpaca quote pagination chronology/bounds violated')
                rows.append(row)  # No sequence ID: preserve ties and multiplicity.
            token = body.get('next_page_token')
            if token is None:
                break
            if not isinstance(token, str) or not token or token in tokens:
                raise ValueError('Invalid/repeated Alpaca page token')
            tokens.add(token); params['page_token'] = token
        else:
            raise ValueError('Stock quote page budget exhausted; incomplete capture')
        manifest = dict(schema=SCHEMA, provider='alpaca', **query, complete=True,
            records=len(rows), records_sha256=identity(rows), page_result_sha256=hashes,
            pages=len(hashes), retrieved_at=datetime.now(timezone.utc).isoformat(),
            availability_basis='historical SIP-feed quote timestamp; local receipt latency unknown',
            timestamp_ties='provider order preserved; ambiguous same-clock states rejected for execution')
        verify_stock_capture(rows,manifest)
        return rows, manifest


class StockQuoteTape:
    def __init__(self, rows, manifest, *, security_id, capture_identity, calendar,
                 legacy_lot_shares=None, size_source_identity=None, policy=QuotePolicy()):
        self.stamps = np.asarray(verify_stock_capture(rows,manifest), dtype=np.int64)
        if not security_id or not capture_identity:
            raise ValueError('Dated stock security and capture identity required')
        if legacy_lot_shares is not None and (type(legacy_lot_shares) is not int
                or legacy_lot_shares <= 0 or not size_source_identity):
            raise ValueError('Legacy round-lot conversion needs an explicit evidence binding')
        self.rows, self.manifest = deepcopy(rows), deepcopy(manifest)
        self.security_id, self.capture_identity, self.calendar = security_id,capture_identity,calendar
        self.legacy_lot_shares, self.size_source_identity = legacy_lot_shares,size_source_identity
        self.policy = policy

    def _quote(self, i):
        t = int(self.stamps[i]); row = self.rows[i]
        lo,hi = self.stamps.searchsorted(t),self.stamps.searchsorted(t,side='right')
        if any(self.rows[j] != row for j in range(lo,hi)):
            return None  # Without sequence IDs there is no proved state ordering.
        values = [row.get(k) for k in ('bp','ap','bs','as')]
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):
            return None
        bp,ap,bs,az = values
        if not 0 < bp <= ap or min(bs,az) <= 0:
            return None
        # Only regular, firm SIP quotes. Unsupported conditions remain observed.
        if row.get('c') != ['R'] or row.get('z') not in ('A','B','C'):
            return None
        date = pd.Timestamp(t,unit='ns',tz='UTC').tz_convert('America/New_York').date().isoformat()
        bounds = self.calendar.bounds(date)
        if bounds is None or not bounds[0].tz_localize('UTC').value <= t < bounds[1].tz_localize('UTC').value:
            return None
        return row

    def first_fill(self, decision_ns, *, side, quantity):
        decision_ns = integer_ns(decision_ns)
        if side not in ('buy','sell') or isinstance(quantity,bool) or not math.isfinite(quantity) or quantity <= 0:
            raise ValueError('Positive stock share quantity and explicit side required')
        start,end = decision_ns+self.policy.latency_ns,decision_ns+self.policy.entry_deadline_ns
        if self.manifest['start_ns'] > start or self.manifest['end_ns'] <= end:
            raise CaptureUnavailable('Stock liquidation window is not completely captured')
        for i in range(self.stamps.searchsorted(start),self.stamps.searchsorted(end,side='right')):
            row = self._quote(i)
            if row is None: continue
            stamp = int(self.stamps[i])
            lot = 1 if stamp >= SIZE_CHANGE else self.legacy_lot_shares
            if lot is None:
                raise CaptureUnavailable('Historical round-lot size evidence missing')
            size = row['as' if side=='buy' else 'bs'] * lot
            if size < quantity: continue
            return dict(symbol=self.manifest['symbol'], security_id=self.security_id, provider='alpaca',
                capture_identity=self.capture_identity, side=side, decision_ns=decision_ns,
                sip_timestamp=stamp, price=float(row['ap' if side=='buy' else 'bp']), reported_size=size,
                provider_size=row['as' if side=='buy' else 'bs'], size_multiplier=lot,
                size_source_identity=self.size_source_identity)
        return None

    def mark(self, clock_ns):
        clock_ns = integer_ns(clock_ns)
        if not self.manifest['start_ns'] <= clock_ns < self.manifest['end_ns']:
            raise CaptureUnavailable('Stock mark clock outside complete capture')
        i = int(self.stamps.searchsorted(clock_ns,side='right'))-1
        if i < 0 or clock_ns-int(self.stamps[i]) > self.policy.max_mark_age_ns or self._quote(i) is None:
            raise QuoteUnavailable('No fresh eligible stock quote state')
        return dict(bid=float(self.rows[i]['bp']),sip_timestamp=int(self.stamps[i]),
            security_id=self.security_id,capture_identity=self.capture_identity,provider='alpaca')


class StockQuoteArchive:
    """Bounded reads of receipt-verified stock captures; one shard per request.

    Shards must fully cover a requested fill/mark window. The demand builder
    must include the required overlap; this reader never bridges missing data.
    """
    def __init__(self, paths, *, calendar, policy=QuotePolicy(), cache_shards=4):
        if type(cache_shards) is not int or cache_shards < 1:
            raise ValueError('Positive bounded stock cache required')
        self.calendar,self.policy,self.limit=calendar,policy,cache_shards
        self.index=[];self.cache=OrderedDict()
        for path in paths:
            path=Path(path); doc=verify(path)
            if doc.get('format')!='v7-frozen-stock-capture-v1':
                raise ValueError('Frozen stock capture required')
            item=doc['capture']
            if doc['identity']!=identity(item):raise ValueError('Stock capture scope changed')
            scope(item['symbol'],item['start_ns'],item['end_ns'])
            if not item.get('security_id') or not item.get('evidence'):
                raise ValueError('Stock security evidence required')
            self.index.append((path,item))
        for i,(path,item) in enumerate(self.index):
            if any(other['symbol']==item['symbol'] and
                   max(other['start_ns'],item['start_ns'])<min(other['end_ns'],item['end_ns'])
                   for _,other in self.index[:i]):
                raise ValueError('Overlapping stock shards require explicit reconciliation')

    def _tape(self, symbol, start, end):
        matches=[(p,c) for p,c in self.index if c['symbol']==symbol and c['start_ns']<=start and c['end_ns']>=end]
        if not matches:raise CaptureUnavailable('No complete stock capture covers this window')
        if len({c['security_id'] for p,c in matches})!=1:
            raise ValueError('Ambiguous dated stock identity')
        # Prefer the narrowest available shard, with deterministic path tie break.
        path,item=min(matches,key=lambda pc:(pc[1]['end_ns']-pc[1]['start_ns'],str(pc[0])))
        if path not in self.cache:
            doc=verify(path,expected_identity=identity(item))
            for source,digest in item['evidence'].items():
                if sha(source)!=digest:raise ValueError('Stock identity/size evidence changed')
            rows=json.loads(gzip.decompress((path/'records.json.gz').read_bytes()))
            manifest=json.loads((path/'capture.json').read_text())
            if any(manifest.get(k)!=item[k] for k in ('symbol','start_ns','end_ns')):
                raise ValueError('Stock capture manifest scope changed')
            self.cache[path]=StockQuoteTape(rows,manifest,security_id=item['security_id'],
                capture_identity=doc['identity'], calendar=self.calendar, policy=self.policy,
                legacy_lot_shares=item.get('legacy_lot_shares'),size_source_identity=item.get('size_source_identity'))
            while len(self.cache)>self.limit:self.cache.popitem(last=False)
        self.cache.move_to_end(path)
        return self.cache[path]

    def first_fill(self,symbol,decision_ns,*,side,quantity):
        return self._tape(symbol,decision_ns+self.policy.latency_ns,
            decision_ns+self.policy.entry_deadline_ns+1).first_fill(decision_ns,side=side,quantity=quantity)

    def mark(self,symbol,clock_ns):
        return self._tape(symbol,max(0,clock_ns-self.policy.max_mark_age_ns),clock_ns+1).mark(clock_ns)
