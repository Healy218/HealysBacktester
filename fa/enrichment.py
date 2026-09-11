"""Capture licensed news, company fundamentals and positioning without backdating."""
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import pandas as pd
import requests
from fa import archive
from scripts.job_receipts import write, record, stamp

RECIPE = 'fa-enrichment-v1'
MASSIVE = 'https://api.massive.com'
ALPACA = 'https://data.alpaca.markets'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def canonical_url(url):
    p = urlsplit(str(url or ''))
    if not p.hostname: return ''
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid', 'ref')]
    return urlunsplit(('https', p.netloc.lower().removeprefix('www.'), p.path.rstrip('/'), urlencode(sorted(query)), ''))


class Client:
    def __init__(self, origin, headers, *, session=None, sleep=time.sleep, interval=0.):
        self.origin, self.headers = origin, headers
        self.session, self.sleep = session or requests.Session(), sleep
        self.interval, self.next_request = interval, 0.

    def get(self, path, params=None):
        url = path if path.startswith('https://') else self.origin + path
        # Never forward credentials to a pagination URL outside the provider.
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.hostname != urlsplit(self.origin).hostname or parsed.port not in (None, 443) or parsed.username:
            raise ValueError('Untrusted provider pagination URL')
        for attempt in range(4):
            delay = self.next_request-time.monotonic()
            if delay>0:self.sleep(delay)
            self.next_request=time.monotonic()+self.interval
            try:
                response = self.session.get(url, params=params, headers=self.headers, timeout=30, allow_redirects=False)
            except requests.RequestException:
                if attempt == 3: raise RuntimeError('Provider network failure') from None
                self.sleep(2 ** attempt); continue
            if response.status_code == 200:
                try: body = response.json()
                except ValueError: raise RuntimeError('Provider returned invalid JSON') from None
                if not isinstance(body, dict): raise ValueError('Provider response must be an object')
                return body
            if response.status_code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise RuntimeError(f'Provider HTTP {response.status_code}')
            retry = response.headers.get('Retry-After', '')
            try: delay = float(retry)
            except ValueError:
                try: delay = (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                except (ValueError, TypeError): delay = min(120,60*2**attempt) if response.status_code==429 else 2 ** attempt
            if delay > 120: raise RuntimeError('Provider retry delay exceeds job budget')
            self.sleep(max(0, delay))
        raise RuntimeError('Provider retries exhausted')

    def pages(self, path, params, *, alpaca=False, max_pages=200):
        seen = set()
        for _ in range(max_pages):
            body = self.get(path, params)
            rows = body.get('news' if alpaca else 'results')
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                raise ValueError('Missing or invalid provider rows')
            yield rows
            cursor = body.get('next_page_token' if alpaca else 'next_url')
            if not cursor: return
            if cursor in seen: raise ValueError('Provider repeated pagination cursor')
            seen.add(cursor)
            if alpaca: params = dict(params, page_token=cursor)
            else: path, params = cursor, None
        raise RuntimeError('Provider page limit reached; checkpoint not advanced')


def clients():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    return {
        'massive': Client(MASSIVE, {'Authorization': 'Bearer ' + os.environ['MASSIVE_API_KEY']}, interval=1.),
        'alpaca': Client(ALPACA, {'APCA-API-KEY-ID': os.environ['ALPACA_API_KEY'], 'APCA-API-SECRET-KEY': os.environ['ALPACA_API_SECRET']}, interval=.35),
    }


def save_records(source, entries, *, captured=None):
    from fa.monthly import locked
    captured = captured or stamp()
    # Keep transitions A -> B -> A while suppressing unchanged polling repeats.
    with locked(archive.config.ARCHIVE / source / '.capture.lock'):
        paths = sorted((archive.config.ARCHIVE / source).glob('*.parquet'))
        latest = {}
        if paths:
            known = pd.concat([pd.read_parquet(p, columns=['record_id','revision','ts_utc']) for p in paths])
            known = known.sort_values('ts_utc').drop_duplicates('record_id', keep='last')
            latest = dict(zip(known.record_id, known.revision))
        rows = []
        for identity, payload in entries:
            identity, revision = str(identity), digest(payload)
            if latest.get(identity) == revision: continue
            rows.append(dict(ts_utc=captured, record_id=identity, revision=revision, payload=json.dumps(payload, sort_keys=True)))
            latest[identity] = revision
        return archive.append(source, pd.DataFrame(rows), key=['record_id','revision','ts_utc'])


def news_record(provider, row):
    identity = str(row['id'])
    published = row['created_at'] if provider == 'alpaca' else row['published_utc']
    pd.Timestamp(published).tz_convert('UTC')
    return identity, dict(provider=provider, provider_id=identity,
        published_at=published, updated_at=row.get('updated_at'),
        title=row.get('headline', row.get('title', '')), url=canonical_url(row.get('url', row.get('article_url', ''))),
        publisher=row.get('source') if provider == 'alpaca' else (row.get('publisher') or {}).get('name'),
        tickers=row.get('symbols', row.get('tickers', [])),
        summary=row.get('summary', row.get('description', '')), content=row.get('content'),
        insights=row.get('insights', []), sentiment_version='massive-provider-unversioned' if provider == 'massive' else None,
        raw=row)


def collect_news(cfg, providers=None, *, now=None):
    providers = providers or clients()
    now = now or datetime.now(timezone.utc)
    result, failed = {}, []
    for provider in ('massive', 'alpaca'):
        name = 'news-' + provider
        started = stamp(); record(cfg['state'], name, 'running', started=started)
        checkpoint = Path(cfg['state']) / name / 'cursor.json'
        # Overlap catches late arrivals/revisions; old history is never backdated.
        start = now - timedelta(days=7)
        if checkpoint.exists(): start = datetime.fromisoformat(json.loads(checkpoint.read_text())['through']) - timedelta(days=2)
        end = now - timedelta(minutes=20) if provider == 'alpaca' else now
        try:
            if start >= end: raise ValueError('Clock moved behind ingestion checkpoint')
            path = '/v1beta1/news' if provider == 'alpaca' else '/v2/reference/news'
            params = dict(start=start.isoformat(), end=end.isoformat(), sort='asc', limit=50, include_content='true') if provider == 'alpaca' else {
                'published_utc.gte': start.isoformat(), 'published_utc.lte': end.isoformat(), 'sort': 'published_utc', 'order': 'asc', 'limit': 1000}
            rows = added = pages = 0
            for batch in providers[provider].pages(path, params, alpaca=provider == 'alpaca'):
                added += save_records('news_' + provider, [news_record(provider, r) for r in batch])
                rows += len(batch); pages += 1
            details = dict(rows=rows, added=added, pages=pages, through=end.isoformat())
            write(checkpoint, details)
            record(cfg['state'], name, 'success', started=started, returncode=0, details=details)
            result[provider] = details
        except Exception as exc:
            record(cfg['state'], name, 'failed', started=started, returncode=1, details={'error_type': type(exc).__name__})
            failed.append(provider)
    if failed: raise RuntimeError('News capture failed: ' + ', '.join(failed))
    return result


DATASETS = {
    'financials': ('/vX/reference/financials', {'timeframe': 'quarterly', 'limit': 5}),
    'short_interest': ('/stocks/v1/short-interest', {'limit': 1, 'sort': 'settlement_date.desc'}),
    'short_volume': ('/stocks/v1/short-volume', {'limit': 1, 'sort': 'date.desc'}),
    'float': ('/stocks/vX/float', {'limit': 1}),
}


def positioning_batch(client, dataset, symbols, now):
    from nn_meta.config import TICKER_ALIASES, FETCH_ALIASES
    datefield={'short_interest':'settlement_date','short_volume':'date','float':'effective_date'}[dataset]
    params={'limit':5000 if dataset=='float' else 50000,'sort':datefield+'.desc,ticker.asc' if dataset!='float' else 'ticker.asc'}
    lower=None
    if dataset!='float':
        lower=(now-timedelta(days=35 if dataset=='short_interest' else 7)).date().isoformat()
        params.update({datefield+'.gte':lower,datefield+'.lte':now.date().isoformat()})
    vendors={symbol:FETCH_ALIASES.get(TICKER_ALIASES.get(symbol,symbol),TICKER_ALIASES.get(symbol,symbol)) for symbol in symbols}
    wanted=set(vendors.values());latest={};count=pages=unmapped=0
    for rows in client.pages(DATASETS[dataset][0],params,max_pages=100):
        pages+=1;count+=len(rows)
        for row in rows:
            ticker=row.get('ticker');date=row.get(datefield)
            if not ticker:
                unmapped+=1;continue
            if not date:raise ValueError('Positioning row lacks date')
            if lower and not lower<=date<=now.date().isoformat():raise ValueError('Provider did not honor positioning date window')
            if date>now.date().isoformat():continue
            if ticker in wanted and (ticker not in latest or date>latest[ticker][datefield]):latest[ticker]=row
    if not count:raise ValueError('Empty market-wide positioning response')
    entries=[]
    for symbol,vendor in vendors.items():
        payload=dict(dataset=dataset,ticker=symbol,provider_ticker=vendor,rows=[latest[vendor]] if vendor in latest else [],source='massive',snapshot_date=now.date().isoformat())
        entries.append((symbol+':'+now.date().isoformat(),payload))
    return entries,dict(pages=pages,provider_rows=count,unmapped_rows=unmapped,window_start=lower)


def collect_fundamentals(cfg, client=None, *, symbols=None, now=None):
    client = client or clients()['massive']
    now = now or datetime.now(timezone.utc)
    symbols = symbols or json.loads(Path(cfg['liquid']).read_text())
    from nn_meta.config import TICKER_ALIASES, FETCH_ALIASES
    results, failed = {}, []
    for dataset, (path, params) in DATASETS.items():
        name = 'fa-' + dataset
        if dataset!='financials':
            started=stamp();record(cfg['state'],name,'running',started=started)
            try:
                entries,counts=positioning_batch(client,dataset,symbols,now)
                counts.update(requested=len(symbols),covered=sum(bool(p['rows']) for _,p in entries),failed=[])
                counts['empty']=len(symbols)-counts['covered'];counts['added']=save_records('fund_'+dataset,entries)
                record(cfg['state'],name,'success',started=started,returncode=0,details=counts)
                results[dataset]=counts;print(json.dumps(dict(dataset=dataset,**counts)),flush=True)
            except Exception as exc:
                record(cfg['state'],name,'failed',started=started,returncode=1,details={'error_type':type(exc).__name__,'reason':str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__})
                failed.append(dataset)
            continue
        previous = Path(cfg['state'])/name/'latest.json'
        resume = previous.exists() and json.loads(previous.read_text()).get('state') != 'success'
        cached = {}
        for p in sorted((archive.config.ARCHIVE/('fund_'+dataset)).glob('*.parquet')):
            for r in pd.read_parquet(p).sort_values('ts_utc').itertuples():
                payload = json.loads(r.payload)
                if payload['snapshot_date'] == now.date().isoformat() and (resume or pd.Timestamp(r.ts_utc)>=pd.Timestamp(now)-pd.Timedelta(hours=4)):cached[payload['ticker']] = payload
        started = stamp(); record(cfg['state'], name, 'running', started=started)
        counts = dict(requested=len(symbols), covered=0, empty=0, added=0, failed=[], error_counts={}, reused=0)
        entries = []
        for index, symbol in enumerate(symbols):
            if not re.fullmatch(r'[A-Z][A-Z0-9.]{0,14}', symbol): raise ValueError('Invalid ticker')
            vendor = TICKER_ALIASES.get(symbol, symbol)
            vendor = FETCH_ALIASES.get(vendor, vendor)
            try:
                if symbol in cached:
                    rows = cached[symbol]['rows'];counts['reused'] += 1
                else:
                    body = client.get(path, dict(params, ticker=vendor))
                    rows = body.get('results')
                if not isinstance(rows, list): raise ValueError('Missing dataset results')
                # These are deliberately bounded latest snapshots, not historical backfills.
                payload = dict(dataset=dataset, ticker=symbol, provider_ticker=vendor, rows=rows, source='massive', snapshot_date=now.date().isoformat())
                entries.append((symbol + ':' + now.date().isoformat(), payload))
                counts['covered' if rows else 'empty'] += 1
            except Exception as exc:
                counts['failed'].append(symbol)
                reason = str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
                counts['error_counts'][reason] = counts['error_counts'].get(reason,0)+1
        counts['added'] = save_records('fund_' + dataset, entries)
        print(json.dumps(dict(dataset=dataset,**counts)),flush=True)
        record(cfg['state'], name, 'failed' if counts['failed'] else 'success', started=started, returncode=1 if counts['failed'] else 0, details=counts)
        results[dataset] = counts
        if counts['failed']: failed.append(dataset)
    # Event disclosures are collected market-wide with bounded date pagination.
    started = stamp(); name = 'fa-disclosures'; record(cfg['state'], name, 'running', started=started)
    try:
        count = added = 0
        params = {'filing_date.gte': (now-timedelta(days=7)).date().isoformat(), 'filing_date.lte': now.date().isoformat(), 'limit': 1000, 'sort': 'filing_date.asc'}
        for rows in client.pages('/stocks/filings/8-K/vX/disclosures', params):
            entries = [(digest(row), dict(dataset='disclosures', raw=row)) for row in rows]
            added += save_records('fund_disclosures', entries); count += len(rows)
        results['disclosures'] = dict(rows=count, added=added)
        record(cfg['state'], name, 'success', started=started, returncode=0, details=results['disclosures'])
    except Exception as exc:
        record(cfg['state'], name, 'failed', started=started, returncode=1, details={'error_type':type(exc).__name__,'reason':str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__})
        failed.append('disclosures')
    if failed: raise RuntimeError('Fundamental capture failed: ' + ', '.join(failed))
    return results
