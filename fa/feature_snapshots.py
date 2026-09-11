"""Immutable, first-observed FA features; no Reddit text or synthetic history."""
import json
import math
import os
from pathlib import Path
import tempfile
import re

import numpy as np
import pandas as pd
from fa.enrichment import digest, canonical_url, RECIPE
from fa.monthly import locked, sha
from scripts.job_receipts import write

NEWS = ['news_count_7d', 'sentiment_mean_7d', 'sentiment_coverage_7d']
FUNDAMENTALS = ['revenue_yoy', 'gross_margin', 'net_margin', 'operating_cash_to_revenue', 'liabilities_to_assets', 'current_ratio', 'shares_yoy']
POSITIONING = ['days_to_cover', 'short_interest', 'short_volume_ratio', 'free_float_percent']
EVENTS = ['disclosures_7d', 'disclosure_categories_7d']
TECHNICAL = ['return_5d', 'return_20d', 'volatility_20d']
GROUPS = dict(news=NEWS, fundamentals=FUNDAMENTALS, positioning=POSITIONING, events=EVENTS)


def read_source(root, source, cutoff, hashes):
    frames = []
    for p in sorted((Path(root)/source).glob('*.parquet')):
        before = sha(p); frame = pd.read_parquet(p)
        if sha(p) != before: raise ValueError('Archive changed during feature read')
        hashes[str(p.relative_to(root))] = before
        ts = pd.to_datetime(frame.ts_utc, utc=True, errors='raise')
        frame = frame[ts <= cutoff].copy(); frame['ts_utc'] = ts[ts <= cutoff]
        frames.append(frame)
    if not frames: return []
    df = pd.concat(frames).sort_values('ts_utc').drop_duplicates(['record_id', 'revision', 'ts_utc'], keep='first')
    # As-of revision selection: later edits cannot rewrite an earlier snapshot.
    df = df.sort_values(['ts_utc', 'revision']).drop_duplicates('record_id', keep='last')
    return [dict(payload=json.loads(r.payload), captured=r.ts_utc, evidence=f'{source}:{r.record_id}:{r.revision}') for r in df.itertuples()]


def news_features(records, symbols, cutoff):
    # Connected components dedupe equal URLs OR exact normalized titles/day.
    # Different distributors always remain one news source family.
    parent = list(range(len(records))); identities = {}
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    valid = []
    for i, row in enumerate(records):
        p = row['payload']; published = pd.Timestamp(p['published_at'])
        if published.tzinfo is None: raise ValueError('News publication needs timezone')
        if published > cutoff or published < cutoff-pd.Timedelta(days=7): continue
        valid.append(i)
        url = canonical_url(p.get('url'))
        title = re.sub(r'\W+', ' ', p.get('title', '').lower()).strip()
        keys = ([('url', url)] if url else []) + ([('title', title, str(published.date()))] if title else [])
        for key in keys:
            if key in identities: parent[find(i)] = find(identities[key])
            else: identities[key] = i
    groups = {}
    for i in valid: groups.setdefault(find(i), []).append(records[i])
    counts = {s: [] for s in symbols}; evidence = {s: [] for s in symbols}
    for rows in groups.values():
        tickers = set(t for r in rows for t in r['payload'].get('tickers', []))
        for ticker in tickers & set(symbols):
            values = []
            for r in sorted(rows, key=lambda r: r['captured'], reverse=True):
                for insight in r['payload'].get('insights') or []:
                    if insight.get('ticker') == ticker and insight.get('sentiment') in ('positive', 'negative', 'neutral'):
                        values.append({'positive':1., 'negative':-1., 'neutral':0.}[insight['sentiment']])
            counts[ticker].append(values[0] if values else np.nan)
            evidence[ticker].extend(r['evidence'] for r in rows)
    out = {}
    for symbol, values in counts.items():
        known = [v for v in values if math.isfinite(v)]
        out[symbol] = dict(news_count_7d=len(values), sentiment_mean_7d=np.mean(known) if known else np.nan,
                           sentiment_coverage_7d=len(known)/len(values) if values else np.nan)
    return out, evidence, len(groups)


def value(row, section, *names):
    fields = row.get('financials', {}).get(section, {})
    for name in names:
        obj = fields.get(name)
        if isinstance(obj, dict) and obj.get('value') is not None:
            try:
                v = float(obj['value'])
                if math.isfinite(v): return v
            except (ValueError, TypeError): pass
    return np.nan


def ratio(numerator, denominator):
    return numerator/denominator if np.isfinite(numerator) and np.isfinite(denominator) and denominator > 0 else np.nan


def financial_features(rows, cutoff):
    rows = [r for r in rows if r.get('end_date') and pd.Timestamp(r['end_date']).date() <= cutoff.date()]
    rows = [r for r in rows if not r.get('acceptance_datetime') or pd.to_datetime(r['acceptance_datetime'],utc=True) <= cutoff]
    rows = [r for r in rows if not r.get('filing_date') or pd.Timestamp(r['filing_date']).date() <= cutoff.date()]
    rows = sorted(rows, key=lambda r:r['end_date'], reverse=True)
    if not rows: return {}
    current = rows[0]
    def year(r):
        try:return int(r.get('fiscal_year', 0))
        except (TypeError,ValueError):return 0
    prior = next((r for r in rows[1:] if r.get('fiscal_period') == current.get('fiscal_period') and
                  year(current)>0 and year(r) == year(current)-1), None)
    def iv(r, *n): return value(r, 'income_statement', *n)
    def bv(*n): return value(current, 'balance_sheet', *n)
    revenue = iv(current, 'revenues')
    shares = iv(current, 'basic_average_shares', 'diluted_average_shares')
    return dict(revenue_yoy=ratio(revenue, iv(prior, 'revenues'))-1 if prior else np.nan,
                gross_margin=ratio(iv(current, 'gross_profit'), revenue),
                net_margin=ratio(iv(current, 'net_income_loss'), revenue),
                operating_cash_to_revenue=ratio(value(current, 'cash_flow_statement', 'net_cash_flow_from_operating_activities'), revenue),
                liabilities_to_assets=ratio(bv('liabilities'), bv('assets')),
                current_ratio=ratio(bv('current_assets'), bv('current_liabilities')),
                shares_yoy=ratio(shares, iv(prior, 'basic_average_shares', 'diluted_average_shares'))-1 if prior else np.nan)


def build_features(cfg, cutoff):
    cutoff = pd.Timestamp(cutoff)
    if cutoff.tzinfo is None: raise ValueError('Feature cutoff needs timezone')
    cutoff = cutoff.tz_convert('UTC')
    symbols = sorted(set(json.loads(Path(cfg['liquid']).read_text())))
    hashes = {}; all_news = []
    for source in ['news_massive', 'news_alpaca']:
        all_news += read_source(cfg['archive'], source, cutoff, hashes)
    from nn_meta.config import TICKER_ALIASES, FETCH_ALIASES
    aliases = {}
    for symbol in symbols:
        vendor = TICKER_ALIASES.get(symbol, symbol)
        vendor = FETCH_ALIASES.get(vendor, vendor)
        aliases.setdefault(vendor, []).append(symbol)
    for row in all_news:
        payload = row['payload']
        payload['tickers'] = list({s for t in payload.get('tickers', []) for s in aliases.get(t, [t])})
        payload['insights'] = [dict(insight, ticker=s) for insight in payload.get('insights') or [] for s in aliases.get(insight.get('ticker'), [insight.get('ticker')])]
    nf, evidence, articles = news_features(all_news, symbols, cutoff)
    data = {s:dict(ticker=s, cutoff=cutoff.isoformat(), **nf[s]) for s in symbols}
    coverage = {}
    for dataset in ['financials', 'short_interest', 'short_volume', 'float']:
        records = read_source(cfg['archive'], 'fund_'+dataset, cutoff, hashes)
        latest = {}
        for r in sorted(records, key=lambda r:r['captured']): latest[r['payload']['ticker']] = r
        coverage[dataset] = 0
        for symbol in symbols:
            r = latest.get(symbol)
            if r is None or cutoff-r['captured'] > pd.Timedelta(days=8): continue
            rows = r['payload']['rows']
            if not rows: continue
            coverage[dataset] += 1; evidence[symbol].append(r['evidence'])
            if dataset == 'financials': data[symbol].update(financial_features(rows, cutoff))
            else:
                datefield = {'short_interest':'settlement_date', 'short_volume':'date', 'float':'effective_date'}[dataset]
                eligible = [x for x in rows if x.get(datefield) and pd.Timestamp(x[datefield]).date() <= cutoff.date()]
                if not eligible: continue
                row = max(eligible, key=lambda x:x[datefield])
                for feature in {'short_interest':['days_to_cover','short_interest'], 'short_volume':['short_volume_ratio'], 'float':['free_float_percent']}[dataset]:
                    data[symbol][feature] = row.get(feature, np.nan)
                data[symbol][dataset+'_age_days'] = (cutoff.date()-pd.Timestamp(row[datefield]).date()).days
    event_records = read_source(cfg['archive'], 'fund_disclosures', cutoff, hashes)
    for symbol in symbols:
        rows = [r for r in event_records if symbol in (r['payload']['raw'].get('tickers') or []) and
                r['payload']['raw'].get('filing_date') and cutoff.date()-pd.Timedelta(days=7) <= pd.Timestamp(r['payload']['raw']['filing_date']).date() <= cutoff.date()]
        # A filing may contain several classified disclosures; count filings once.
        data[symbol].update(disclosures_7d=len(set(r['payload']['raw'].get('accession_number', r['evidence']) for r in rows)),
                            disclosure_categories_7d=len(set(r['payload']['raw'].get('primary_category') for r in rows)))
        evidence[symbol].extend(r['evidence'] for r in rows)
    price_hashes = {}
    for symbol in symbols:
        p = Path(cfg['prices'])/(symbol+'.parquet')
        if not p.exists(): continue
        before=sha(p); frame=pd.read_parquet(p)
        if sha(p)!=before: raise ValueError('Prices changed during feature read')
        close=frame.Close.copy();close.index=pd.to_datetime(close.index,utc=True)
        close=close[close.index < cutoff.normalize()].sort_index()
        if len(close)<21 or close.index.has_duplicates or not ((close>0)&np.isfinite(close)).all(): continue
        returns=close.pct_change(fill_method=None)
        data[symbol].update(return_5d=close.iloc[-1]/close.iloc[-6]-1, return_20d=close.iloc[-1]/close.iloc[-21]-1,
                            volatility_20d=returns.iloc[-20:].std(), price_as_of=close.index[-1].isoformat())
        price_hashes[symbol]=before
    frame=pd.DataFrame(data.values())
    for col in TECHNICAL + sum(GROUPS.values(), []):
        if col not in frame: frame[col]=np.nan
        frame[col]=pd.to_numeric(frame[col],errors='coerce').replace([np.inf,-np.inf],np.nan)
    metadata=dict(recipe=RECIPE, cutoff=cutoff.isoformat(), symbols=len(symbols), unique_news=articles,
        raw_sha256=hashes, price_sha256=price_hashes, coverage=coverage,
        feature_nonmissing={c:int(frame[c].notna().sum()) for c in TECHNICAL+sum(GROUPS.values(),[])},
        source_families=['news','company_filings','market_positioning'],
        sentiment_version='massive-provider-unversioned; categorical mapping v1',
        training_scope='experimental; no automatic production or universe promotion')
    return frame, metadata, evidence


def snapshot(cfg, *, cutoff=None):
    from datetime import datetime, timezone
    from scripts.check_ops_health import check_job
    cutoff=pd.Timestamp.now(tz='UTC') if cutoff is None else pd.Timestamp(cutoff)
    now=datetime.now(timezone.utc)
    for job, hours in [('news-massive',3),('news-alpaca',3),('fa-fundamentals',48),('fa-prices',48)]:
        if not check_job(Path(cfg['state'])/job,hours*3600,now)['healthy']: raise ValueError('Snapshot input job unhealthy: '+job)
    calendar=json.loads(Path(cfg['calendar']).read_text())
    expected=max(s['date'] for s in calendar['sessions'] if s['date']<str(cutoff.tz_convert('UTC').date()))
    price_manifest=json.loads((Path(cfg['prices'])/'manifest.json').read_text())
    if price_manifest['last']!=expected:raise ValueError('Prices do not include the latest completed input date')
    root=Path(cfg['enrichment_snapshots']);root.mkdir(parents=True,exist_ok=True)
    name=cutoff.tz_convert('UTC').strftime('%Y%m%dT%H%M%S%fZ')
    with locked(root/'.snapshot.lock'), locked(Path(cfg['prices'])/'.prices.lock'):
        frame, meta, evidence=build_features(cfg,cutoff)
        with tempfile.TemporaryDirectory(prefix='.pending-',dir=root) as temp:
            stage=Path(temp);frame.to_parquet(stage/'features.parquet',index=False)
            write(stage/'evidence.json',evidence)
            meta['files']={p.name:sha(p) for p in stage.iterdir()}
            meta['code_sha256']={p.name:sha(p) for p in [Path(__file__),Path(__file__).with_name('enrichment.py')]}
            write(stage/'manifest.json',meta)
            os.rename(stage,root/name)
    return dict(snapshot=str(root/name),**meta)
