import gzip
import json
from types import SimpleNamespace

import pandas as pd
import pytest

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.execution import CaptureUnavailable, QuoteUnavailable
from nn_meta.v7.stock_quotes import AlpacaStockQuotes, StockQuoteTape, StockQuoteArchive, scope, SCHEMA
from nn_meta.v7.storage import identity,receipt,sha


def ns(t):return int(pd.Timestamp(t).value)


def quote(t,**kwargs):
    return dict(t=t,bp=100.,ap=100.1,bs=2,**{'as':3},c=['R'],z='C',**kwargs)


def tape(rows,date='2022-05-05'):
    start=ns(date+'T13:30:00Z');end=start+120_000_000_000
    manifest=dict(schema=SCHEMA,provider='alpaca',**scope('AAPL',start,end),complete=True,
        records=len(rows),records_sha256=identity(rows))
    calendar=SimpleNamespace(bounds=lambda d:(pd.Timestamp(d+' 13:30'),pd.Timestamp(d+' 20:00')))
    return StockQuoteTape(rows,manifest,security_id='apple',capture_identity='capture',calendar=calendar,
        legacy_lot_shares=100,size_source_identity='dated-size-evidence')


class Session:
    def __init__(self,pages):self.pages=iter(pages);self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append((url,{**kwargs,'params':dict(kwargs['params'])}))
        body=next(self.pages)
        return SimpleNamespace(status_code=200,json=lambda:body)


def test_complete_paginated_capture_exact_nanoseconds_no_mapping():
    start=ns('2022-05-05T13:30:00Z');end=start+60_000_000_001
    a=quote('2022-05-05T13:30:00.000000001Z');b=quote('2022-05-05T13:31:00.000000000Z')
    session=Session([{'quotes':{'AAPL':[a]},'next_page_token':'two'},
                     {'quotes':{'AAPL':[b]},'next_page_token':None}])
    rows,m=AlpacaStockQuotes(session=session,key='fake',secret='fake').capture('AAPL',start,end)
    assert rows==[a,b] and m['complete'] and m['pages']==2
    assert session.calls[0][1]['params']['end']=='2022-05-05T13:31:00+00:00'
    assert session.calls[0][1]['params']['asof']=='-'
    assert session.calls[0][1]['params']['feed']=='sip'
    assert session.calls[1][1]['params']['page_token']=='two'
    assert all(c[1]['allow_redirects'] is False for c in session.calls)


@pytest.mark.parametrize('pages,match',[
    ([{'quotes':{'OTHER':[]}}],'unrequested'),
    ([{'quotes':{'AAPL':[]},'next_page_token':'x'}]*2,'repeated'),
    ([{'quotes':{'AAPL':[]},'next_page_token':''}],'Invalid'),
    ([{'quotes':None}],'mapping'),
    ([{'quotes':{'AAPL':[quote('2022-05-05T13:31:00Z')]}}],'bounds'),
])
def test_capture_rejects_wrong_scope_incomplete_pages(pages,match):
    with pytest.raises(ValueError,match=match):
        AlpacaStockQuotes(session=Session(pages),key='fake',secret='fake').capture(
            'AAPL',ns('2022-05-05T13:30:00Z'),ns('2022-05-05T13:31:00Z'))


def test_page_budget_empty_complete_and_clock_precision():
    s=ns('2022-05-05T13:30:00Z')
    with pytest.raises(ValueError,match='budget'):
        AlpacaStockQuotes(session=Session([{'quotes':{},'next_page_token':'more'}]),key='fake',secret='fake').capture('AAPL',s,s+1,max_pages=1)
    rows,m=AlpacaStockQuotes(session=Session([{'quotes':{}}]),key='fake',secret='fake').capture('AAPL',s,s+1)
    assert rows==[] and m['complete']
    with pytest.raises(ValueError,match='UTC'):
        tape([quote('2022-05-05T13:30:01.1234567890Z')])


@pytest.mark.parametrize('date,size',[('2025-10-31',200),('2025-11-03',2)])
def test_quote_size_transition_is_dated(date,size):
    t=tape([quote(date+'T13:30:01Z')],date)
    fill=t.first_fill(ns(date+'T13:30:00Z'),side='sell',quantity=1)
    assert fill['reported_size']==size
    assert fill['security_id']=='apple' and fill['provider']=='alpaca'
    assert t.first_fill(ns(date+'T13:30:00Z'),side='sell',quantity=size+1) is None


def test_fill_requires_complete_window_and_legacy_size_evidence():
    t=tape([quote('2022-05-05T13:30:01Z')]);t.legacy_lot_shares=None
    with pytest.raises(CaptureUnavailable,match='round-lot'):
        t.first_fill(ns('2022-05-05T13:30:00Z'),side='sell',quantity=1)
    with pytest.raises(CaptureUnavailable,match='completely'):
        t.first_fill(ns('2022-05-05T13:31:01Z'),side='sell',quantity=1)


def test_latest_invalid_state_never_uses_older_mark_and_future_is_ignored():
    good=quote('2022-05-05T13:30:01Z');bad={**quote('2022-05-05T13:30:02Z'),'bp':101.}
    future={**quote('2022-05-05T13:30:04Z'),'bp':99.}
    t=tape([good,bad,future])
    assert t.mark(ns('2022-05-05T13:30:01.999999999Z'))['bid']==100
    with pytest.raises(QuoteUnavailable):t.mark(ns('2022-05-05T13:30:03Z'))
    with pytest.raises(QuoteUnavailable):t.mark(ns('2022-05-05T13:31:00Z'))
    assert t.first_fill(ns('2022-05-05T13:30:01Z'),side='sell',quantity=1)['price']==99


def test_ambiguous_same_timestamp_and_nonregular_quotes_are_not_executable():
    q=quote('2022-05-05T13:30:01Z')
    t=tape([q,{**q,'bp':99.}])
    assert t.first_fill(ns('2022-05-05T13:30:00Z'),side='sell',quantity=1) is None
    with pytest.raises(QuoteUnavailable):t.mark(ns('2022-05-05T13:30:01Z'))
    for override in ({'c':['H']},{'bs':0},{'z':'D'}):
        assert tape([{**q,**override}]).first_fill(ns('2022-05-05T13:30:00Z'),side='buy',quantity=1) is None


def test_archive_receipts_scope_and_security_binding(tmp_path):
    t=tape([quote('2022-05-05T13:30:01Z')]);p=tmp_path/'capture';p.mkdir()
    evidence=tmp_path/'identity.json';evidence.write_text('dated identity')
    item={k:t.manifest[k] for k in ('symbol','start_ns','end_ns')}
    item.update(security_id='apple',legacy_lot_shares=100,size_source_identity='size',evidence={str(evidence):sha(evidence)})
    (p/'records.json.gz').write_bytes(gzip.compress(json.dumps(t.rows).encode()))
    (p/'capture.json').write_text(json.dumps(t.manifest))
    receipt(p,{'format':'v7-frozen-stock-capture-v1','capture':item,'identity':identity(item)})
    archive=StockQuoteArchive([p],calendar=t.calendar)
    assert archive.first_fill('AAPL',ns('2022-05-05T13:30:00Z'),side='sell',quantity=150)['reported_size']==200
    with pytest.raises(CaptureUnavailable):archive.first_fill('OTHER',ns('2022-05-05T13:30:00Z'),side='sell',quantity=1)
    evidence.write_text('changed')
    with pytest.raises(ValueError,match='evidence changed'):
        StockQuoteArchive([p],calendar=t.calendar).first_fill('AAPL',ns('2022-05-05T13:30:00Z'),side='sell',quantity=1)


def test_request_binds_dated_listed_identity_and_exclusions(tmp_path):
    from scripts.capture_v7_stock_quotes import prepare_request
    ref=tmp_path/'reference';ref.mkdir()
    (ref/'response.json').write_text(json.dumps({'results':{'ticker':'AAPL','composite_figi':'apple',
        'market':'stocks','locale':'us','primary_exchange':'XNAS'}}))
    receipt(ref,{'http_status':200,'query':{'params':{'date':'2022-05-05'},'path':'/v3/reference/tickers/AAPL'}})
    units=tmp_path/'units';units.mkdir();(units/'response.bin').write_bytes(b'primary size evidence')
    receipt(units,{'query':{'url':'https://docs.alpaca.markets/example'}})
    row=dict(symbol='AAPL',security_id='apple',start_ns=ns('2022-05-05T13:30:00Z'),
        end_ns=ns('2022-05-05T13:32:00Z'),identity_reference=str(ref),legacy_lot_shares=100,
        size_evidence=[str(units)])
    item=prepare_request(row,{'apple'})
    assert item['asof']=='-' and item['feed']=='sip' and len(item['evidence'])==4
    with pytest.raises(ValueError,match='non-OTC'):prepare_request(row,set())
    with pytest.raises(ValueError,match='Exact-date'):
        prepare_request({**row,'security_id':'reused-ticker-company'},{'reused-ticker-company'})
    with pytest.raises(ValueError,match='Exact-date'):
        prepare_request({**row,'start_ns':ns('2022-05-06T13:30:00Z'),'end_ns':ns('2022-05-06T13:32:00Z')},{'apple'})


def test_stock_fill_is_consumed_by_funded_inventory_ledger():
    from nn_meta.v7.physical import PhysicalLedger,SettlementCalendar
    days=['2022-05-05','2022-05-06','2022-05-09','2022-05-10']
    t=tape([quote('2022-05-05T13:30:01Z')])
    calendar=SimpleNamespace(sessions=days,bounds=t.calendar.bounds)
    settlement=SettlementCalendar(dict(schema='v7-settlement-calendar-v1',source_identity='fixture',
        coverage_start=days[0],coverage_end=days[-1],business_dates=days),calendar)
    ledger=PhysicalLedger(settlement_calendar=settlement)
    fill=t.first_fill(ns('2022-05-05T13:30:00Z'),side='buy',quantity=200)
    assert ledger.acquire_inventory('stock','AAPL','apple',200,fill)
    assert ledger.reconcile()['pending_settlements']==1
    ledger.settle(ns('2022-05-10T13:30:00Z'))
    assert ledger.shares[('AAPL','apple')]==200
    assert ledger.reconcile()['pending_settlements']==0
