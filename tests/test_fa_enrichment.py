from pathlib import Path
from datetime import datetime, timezone
import json
import numpy as np
import pandas as pd
import pytest
from fa import enrichment as en
from fa import feature_snapshots as fs
from fa.evaluate_features import evaluate, load_panel, predict

class Response:
    def __init__(self,status,body,headers=None):self.status_code=status;self.body=body;self.headers=headers or {}
    def json(self):return self.body
class Session:
    def __init__(self,responses):self.responses=iter(responses);self.calls=[]
    def get(self,*a,**kw):self.calls.append((a,kw));return next(self.responses)


def test_pagination_retries_and_never_sends_credentials_to_other_host():
    s=Session([Response(429,{}, {'Retry-After':'0'}),Response(200,{'results':[{'id':1}],'next_url':'https://evil.test/steal'})])
    c=en.Client(en.MASSIVE,{'Authorization':'private'},session=s,sleep=lambda _:None)
    pages=c.pages('/v2/reference/news',{})
    assert next(pages)==[{'id':1}]
    with pytest.raises(ValueError,match='Untrusted'):next(pages)
    assert len(s.calls)==2 and not s.calls[0][1]['allow_redirects']


def test_repeated_cursor_and_missing_rows_fail_closed():
    url=en.MASSIVE+'/next'
    c=en.Client(en.MASSIVE,{},session=Session([Response(200,{'results':[],'next_url':url})]*3))
    with pytest.raises(ValueError,match='repeated'):list(c.pages('/first',{}))
    c=en.Client(en.MASSIVE,{},session=Session([Response(200,{'status':'OK'})]))
    with pytest.raises(ValueError,match='Missing'):list(c.pages('/first',{}))


def test_alpaca_page_tokens_keep_original_filters():
    s=Session([Response(200,{'news':[{'id':1}],'next_page_token':'two'}),Response(200,{'news':[{'id':2}]})])
    c=en.Client(en.ALPACA,{},session=s)
    assert len(list(c.pages('/v1beta1/news',{'start':'fixed'},alpaca=True)))==2
    assert s.calls[1][1]['params']=={'start':'fixed','page_token':'two'}


def test_failed_page_preserves_checkpoint_and_other_provider_runs(tmp_path,monkeypatch):
    monkeypatch.setattr(en.archive.config,'ARCHIVE',tmp_path/'archive')
    p=tmp_path/'state/news-massive/cursor.json';p.parent.mkdir(parents=True);p.write_text('{"through":"2026-09-08T00:00:00+00:00"}')
    original=p.read_bytes()
    class Broken:
        def pages(self,*a,**kw):
            yield [dict(id='one',published_utc='2026-09-09T00:00:00Z',tickers=['AAPL'])]
            raise RuntimeError('page two failed')
    class Empty:
        def pages(self,*a,**kw):yield []
    with pytest.raises(RuntimeError,match='massive'):
        en.collect_news({'state':str(tmp_path/'state')},{'massive':Broken(),'alpaca':Empty()},now=datetime(2026,9,10,tzinfo=timezone.utc))
    assert p.read_bytes()==original
    assert json.loads((tmp_path/'state/news-alpaca/latest.json').read_text())['state']=='success'


def test_revisions_keep_first_capture_and_asof_selects_known_revision(tmp_path,monkeypatch):
    monkeypatch.setattr(en.archive.config,'ARCHIVE',tmp_path)
    old={'ticker':'AAPL','rows':[]};new={'ticker':'AAPL','rows':[{'changed':1}]}
    en.save_records('fund_test',[('a',old)],captured='2026-09-08T12:00Z')
    en.save_records('fund_test',[('a',old)],captured='2026-09-09T12:00Z')
    en.save_records('fund_test',[('a',new)],captured='2026-09-10T12:00Z')
    rows=fs.read_source(tmp_path,'fund_test',pd.Timestamp('2026-09-09T23:00Z'),{})
    assert len(rows)==1 and rows[0]['payload']==old and rows[0]['captured']==pd.Timestamp('2026-09-08T12:00Z')
    assert fs.read_source(tmp_path,'fund_test',pd.Timestamp('2026-09-11T20:00Z'),{})[0]['payload']==new


def article(url,title,tickers,sentiment=None,captured='2026-09-10T12:00Z'):
    return dict(captured=pd.Timestamp(captured),evidence=url,payload=dict(url=url,title=title,tickers=tickers,
        published_at='2026-09-10T10:00Z',insights=[dict(ticker='AAPL',sentiment=sentiment)] if sentiment else []))


def test_cross_provider_story_dedup_and_ticker_specific_sentiment():
    records=[article('http://www.example.com/story?utm_source=x','Apple update',['AAPL','MSFT']),
             article('https://example.com/story','Apple update',['AAPL'],'negative'),
             article('https://syndicate.com/other','Apple update',['AAPL'],'negative')]
    features,evidence,n=fs.news_features(records,['AAPL','MSFT'],pd.Timestamp('2026-09-10T23:00Z'))
    assert n==1 and features['AAPL']['news_count_7d']==1 and features['AAPL']['sentiment_mean_7d']==-1
    assert features['MSFT']['news_count_7d']==1 and np.isnan(features['MSFT']['sentiment_mean_7d'])
    assert len(evidence['AAPL'])==3


def test_news_published_future_is_not_a_current_feature():
    row=article('https://example.com/a','a',['AAPL']);row['payload']['published_at']='2026-09-11T00:00Z'
    f,_,n=fs.news_features([row],['AAPL'],pd.Timestamp('2026-09-10T23:00Z'))
    assert n==0 and f['AAPL']['news_count_7d']==0


def test_financial_growth_uses_matching_quarter_and_missing_is_not_zero():
    def row(year,quarter,revenue):return dict(end_date=f'{year}-06-30',fiscal_year=str(year),fiscal_period=quarter,
        financials={'income_statement':{'revenues':{'value':revenue}}})
    f=fs.financial_features([row(2026,'Q2',120),row(2025,'Q1',10),row(2025,'Q2',100)],pd.Timestamp('2026-09-10T23:00Z'))
    assert f['revenue_yoy']==pytest.approx(.2) and np.isnan(f['gross_margin'])


def test_empty_evaluation_does_not_claim_improvement():
    r=evaluate(pd.DataFrame());assert r['status']=='awaiting-forward-outcomes' and 'metrics' not in r


def test_purged_evaluation_never_trains_on_future_labels():
    rng=np.random.default_rng(2);rows=[]
    dates=pd.bdate_range('2025-01-01',periods=120,tz='UTC')
    for i in range(105):
        for symbol in ['A','B','C','D']:
            r=dict(ticker=symbol,cutoff=dates[i]-pd.Timedelta(hours=2),entry_date=dates[i],label_end=dates[i+5],target=rng.normal(0,.02))
            r.update({c:rng.normal() for c in fs.TECHNICAL+sum(fs.GROUPS.values(),[])});rows.append(r)
    r=evaluate(pd.DataFrame(rows),min_train_days=40,min_test_days=10)
    assert r['status']=='evaluated-experimental-only' and len(r['metrics'])==6
    assert all(pd.Timestamp(f['train_label_end'])<pd.Timestamp(f['first_test_cutoff']) for f in r['folds'])
    assert len(set(m['rows'] for m in r['metrics'].values()))==1


def test_imputation_uses_training_only():
    train=pd.DataFrame({'a':[1.,2.,np.nan,4.],'target':[.1,.2,.3,.4]})
    first=pd.DataFrame({'a':[np.nan]});larger=pd.DataFrame({'a':[np.nan,1e12]})
    assert predict(train,first,['a'])[0]==pytest.approx(predict(train,larger,['a'])[0])


def test_snapshot_requires_completed_input_jobs(tmp_path):
    with pytest.raises(ValueError,match='unhealthy'):
        fs.snapshot(dict(state=str(tmp_path)),cutoff='2026-09-10T23:00Z')


def test_provider_reversion_is_a_new_observation(tmp_path,monkeypatch):
    monkeypatch.setattr(en.archive.config,'ARCHIVE',tmp_path)
    for day,payload in [(8,{'v':1}),(9,{'v':2}),(10,{'v':1})]:
        en.save_records('news_test',[('a',payload)],captured=f'2026-09-{day:02d}T12:00Z')
    latest=fs.read_source(tmp_path,'news_test',pd.Timestamp('2026-09-10T23:00Z'),{})
    assert latest[0]['payload']=={'v':1} and latest[0]['captured']==pd.Timestamp('2026-09-10T12:00Z')


def test_future_filing_cannot_supply_fundamentals():
    row=dict(end_date='2026-06-30',filing_date='2026-09-11',financials={})
    assert fs.financial_features([row],pd.Timestamp('2026-09-10T23:00Z'))=={}


def test_feature_panel_excludes_future_captures_and_keeps_filings_distinct(tmp_path,monkeypatch):
    root=tmp_path/'archive';monkeypatch.setattr(en.archive.config,'ARCHIVE',root)
    universe=tmp_path/'universe.json';universe.write_text('["AAPL","SPY"]')
    prices=tmp_path/'prices';prices.mkdir()
    pd.DataFrame({'Close':np.arange(100.,130.)},index=pd.bdate_range('2026-07-01',periods=30)).to_parquet(prices/'AAPL.parquet')
    p=article('https://example.com/a','Apple update',['AAPL'],'positive')['payload']
    en.save_records('news_massive',[('one',p)],captured='2026-09-10T12:00Z')
    en.save_records('news_alpaca',[('two',p)],captured='2026-09-11T12:00Z')
    event=dict(accession_number='filing-1',filing_date='2026-09-10',tickers=['AAPL'],primary_category='management')
    en.save_records('fund_disclosures',[('e',dict(raw=event))],captured='2026-09-10T12:00Z')
    en.save_records('fund_disclosures',[('e2',dict(raw=dict(event,primary_category='agreement')))],captured='2026-09-10T12:00Z')
    frame,meta,evidence=fs.build_features(dict(archive=root,prices=prices,liquid=universe),pd.Timestamp('2026-09-10T23:00Z'))
    a=frame.set_index('ticker').loc['AAPL']
    assert a.news_count_7d==1 and a.disclosures_7d==1 and a.disclosure_categories_7d==2
    assert np.isnan(a.revenue_yoy) and a.return_5d>0
    assert all('news_alpaca' not in x for x in evidence['AAPL'])
    assert meta['feature_nonmissing']['return_5d']==1


def test_outcomes_cannot_start_before_snapshot_and_hash_tampering_rejected(tmp_path):
    from fa.monthly import sha
    folder=tmp_path/'snapshots/20260910T230000Z';folder.mkdir(parents=True)
    prices=tmp_path/'prices';prices.mkdir()
    cutoff='2026-09-10T23:00:00+00:00'
    frame=pd.DataFrame([dict(ticker='AAPL',cutoff=cutoff,**{c:.1 for c in fs.TECHNICAL})])
    frame.to_parquet(folder/'features.parquet',index=False)
    (folder/'manifest.json').write_text(json.dumps(dict(recipe='test',cutoff=cutoff,files={'features.parquet':sha(folder/'features.parquet')})))
    pd.DataFrame({'Close':np.arange(100.,120.)},index=pd.bdate_range('2026-09-01',periods=20)).to_parquet(prices/'AAPL.parquet')
    calendar=tmp_path/'calendar.json';calendar.write_text(json.dumps({'sessions':[{'date':str(d.date()),'close':'16:00'} for d in pd.bdate_range('2026-09-01',periods=20)]}))
    panel,_=load_panel(tmp_path/'snapshots',prices,calendar=calendar)
    assert panel.iloc[0].entry_date==pd.Timestamp('2026-09-11T20:00Z')
    assert panel.iloc[0].label_end==pd.Timestamp('2026-09-18T20:00Z')
    (folder/'features.parquet').write_bytes(b'changed')
    with pytest.raises(ValueError,match='hash mismatch'):load_panel(tmp_path/'snapshots',prices,calendar=calendar)


def test_preopen_snapshot_uses_same_day_close_and_early_close_is_respected(tmp_path):
    from fa.monthly import sha
    snapshots=tmp_path/'snapshots';prices=tmp_path/'prices';prices.mkdir()
    dates=pd.bdate_range('2026-09-01',periods=20)
    pd.DataFrame({'Close':np.arange(100.,120.)},index=dates).to_parquet(prices/'AAPL.parquet')
    calendar=tmp_path/'calendar.json'
    calendar.write_text(json.dumps({'sessions':[{'date':str(d.date()),'close':'13:00' if str(d.date())=='2026-09-10' else '16:00'} for d in dates]}))
    for hour in [1,18]:
        folder=snapshots/f'20260910T{hour:02d}0000Z';folder.mkdir(parents=True)
        cutoff=f'2026-09-10T{hour:02d}:00:00+00:00'
        frame=pd.DataFrame([dict(ticker='AAPL',cutoff=cutoff,**{c:.1 for c in fs.TECHNICAL})]);frame.to_parquet(folder/'features.parquet',index=False)
        (folder/'manifest.json').write_text(json.dumps(dict(recipe='test',cutoff=cutoff,files={'features.parquet':sha(folder/'features.parquet')})))
        panel,_=load_panel(snapshots,prices,calendar=calendar)
        assert panel.iloc[0].entry_date==pd.Timestamp('2026-09-10T17:00Z' if hour==1 else '2026-09-11T20:00Z')


def test_partial_fundamental_retry_reuses_successful_captures(tmp_path,monkeypatch):
    monkeypatch.setattr(en.archive.config,'ARCHIVE',tmp_path/'archive')
    class Partial:
        def __init__(self,fail):self.fail=fail;self.calls=[]
        def get(self,path,params):
            self.calls.append((path,params['ticker']))
            if self.fail and params['ticker']=='MSFT':raise RuntimeError('Provider HTTP 503')
            return {'results':[]}
        def pages(self,path,*a,**kw):
            if 'disclosures' in path:yield []
            else:yield [dict(ticker='AAPL',settlement_date='2026-09-09',date='2026-09-09',effective_date='2026-09-09')]
    cfg={'state':str(tmp_path/'state')};now=datetime(2026,9,10,tzinfo=timezone.utc)
    with pytest.raises(RuntimeError):en.collect_fundamentals(cfg,Partial(True),symbols=['AAPL','MSFT'],now=now)
    second=Partial(False);out=en.collect_fundamentals(cfg,second,symbols=['AAPL','MSFT'],now=now)
    assert len(second.calls)==1 and all(t=='MSFT' for _,t in second.calls)
    assert out['financials']['reused']==1 and out['financials']['empty']==2
    assert all(out[k]['covered']==1 and out[k]['empty']==1 for k in en.DATASETS if k!='financials')


def test_headerless_throttle_uses_long_backoff():
    delays=[]
    c=en.Client(en.MASSIVE,{},session=Session([Response(429,{}),Response(200,{'results':[]})]),sleep=delays.append)
    assert c.get('/test')=={'results':[]}
    assert delays==[60]


def test_bulk_positioning_keeps_latest_requested_tickers():
    class Bulk:
        def pages(self,path,params,**kw):
            assert params['limit']==5000 and params['settlement_date.gte']=='2026-08-06'
            yield [dict(ticker='AAPL',settlement_date='2026-09-01',short_interest=10),dict(ticker='OTHER',settlement_date='2026-09-09')]
            yield [dict(ticker='AAPL',settlement_date='2026-09-09',short_interest=20)]
    rows,meta=en.positioning_batch(Bulk(),'short_interest',['AAPL','MSFT'],datetime(2026,9,10,tzinfo=timezone.utc))
    assert rows[0][1]['rows'][0]['short_interest']==20 and rows[1][1]['rows']==[]
    assert meta['pages']==2 and meta['provider_rows']==3


@pytest.mark.parametrize('rows',[[],[dict(ticker='AAPL',date='2026-08-01')],[dict(ticker='AAPL')]])
def test_bulk_positioning_rejects_empty_or_invalid_window(rows):
    class Bulk:
        def pages(self,*a,**kw):yield rows
    with pytest.raises(ValueError):en.positioning_batch(Bulk(),'short_volume',['AAPL'],datetime(2026,9,10,tzinfo=timezone.utc))
