"""Bounded Alpaca GET controls for pagination, feed parameters and old metadata."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nn_meta.etfe.alpaca_probe import ReadOnlyProbe
from nn_meta.etfe.preparation import file_sha, save_new
from nn_meta.etfe.vwap_setup import verify

CONTRACTS = ('SPY240119C00475000', 'QQQ240119C00409780', 'VOO240119C00435000')
PRICE_CONDITIONS = frozenset('HIJSabcdefghijklmnopqrs')
VOLUME_ONLY = frozenset('tu')
EXCLUDED = frozenset('ABCDEFG')


def pages(client, route, params, field, *, max_pages=16):
    """Keep occurrences; short/empty pages with a token are not completion."""
    records, tokens, receipt_ids = {}, set(), []
    query = dict(params)
    for _ in range(max_pages):
        receipt, body = client.get(route, query)
        receipt_ids.append(len(client.receipts)-1)
        if receipt['status_code'] != 200 or receipt['transport_error'] or not isinstance(body, dict):
            return dict(complete=False, reason='request_failed', receipts=receipt_ids, records=records)
        values = body.get(field) or {}
        if not isinstance(values, dict):
            return dict(complete=False, reason='unexpected_schema', receipts=receipt_ids, records=records)
        for symbol, rows in values.items():
            records.setdefault(symbol, []).extend(rows)
        token = body.get('next_page_token')
        if not token:
            return dict(complete=True, reason='terminal_page', receipts=receipt_ids, records=records)
        if token in tokens:
            return dict(complete=False, reason='repeated_token', receipts=receipt_ids, records=records)
        tokens.add(token)
        query = dict(params, page_token=token)
    return dict(complete=False, reason='page_cap', receipts=receipt_ids, records=records)


def aggregate(trades):
    """Independent minute reconciliation with Decimal, not a fill engine."""
    buckets = {}
    for row in trades:
        minute = row['t'][:16]+':00Z'
        b = buckets.setdefault(minute, dict(prices=[], notional=Decimal(0),
            price_volume=Decimal(0), volume=Decimal(0), count=0, conditions=Counter(), unknown=[]))
        c, price, size = row['c'], Decimal(str(row['p'])), Decimal(str(row['s']))
        b['conditions'][c] += 1
        if c in PRICE_CONDITIONS:
            b['prices'].append(price)
            b['notional'] += price*size
            b['price_volume'] += size
        if c in PRICE_CONDITIONS | VOLUME_ONLY:
            b['volume'] += size
            b['count'] += 1
        elif c not in EXCLUDED:
            b['unknown'].append(c)
    result = {}
    for stamp, b in buckets.items():
        p = b['prices']
        result[stamp] = dict(o=float(p[0]) if p else None, c=float(p[-1]) if p else None,
            h=float(max(p)) if p else None, l=float(min(p)) if p else None,
            v=float(b['volume']), n=b['count'],
            vw=float(b['notional']/b['price_volume']) if b['price_volume'] else None,
            vwap_volume=float(b['price_volume']), conditions=dict(b['conditions']), unknown=b['unknown'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--followup', action='store_true', help='Page-size 2 and older-catalog controls only')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != ROOT/'nn_meta/validation' or not output.name.startswith('etfe-'):
        parser.error('Fresh direct ETFE validation root required')
    setup = verify(ROOT/'nn_meta/validation/etfe-setup-20261003-vwap-r1')
    from dotenv import dotenv_values
    values = dotenv_values(ROOT/'.env')
    credentials = {role:(values.get(key),values.get(secret)) for role,key,secret in (
        ('data','ALPACA_API_KEY','ALPACA_API_SECRET'),
        ('metadata','ALPACA_PAPER_API_KEY','ALPACA_PAPER_API_SECRET'))}
    if not all(all(pair) for pair in credentials.values()):
        parser.error('Credential pairs missing')
    client = ReadOnlyProbe(output, credentials, max_requests=64)
    if args.followup:
        followup(client, setup)
        return
    findings = {}
    params = dict(symbols=','.join(CONTRACTS), start='2024-01-18T14:30:00Z',
                  end='2024-01-18T14:30:59.999999999Z', sort='asc', limit=10000)
    large = pages(client, 'option_trades', params, 'trades')
    findings['large_page'] = large
    if not large['complete']:
        save_new(output/'PARTIAL.json', findings)
        raise SystemExit('Initial request failed; stopped without dependent controls')
    small = pages(client, 'option_trades', dict(params, limit=50), 'trades')
    findings['pagination'] = dict(complete=small['complete'], receipts=small['receipts'],
        same_occurrences=large['records']==small['records'], reason=small['reason'],
        counts={s:len(v) for s,v in large['records'].items()})
    bars = pages(client, 'option_bars', dict(params, timeframe='1Min'), 'bars')
    findings['bars'] = bars
    findings['reconciliation'] = []
    for symbol, trades in large['records'].items():
        expected = aggregate(trades)
        for bar in bars['records'].get(symbol, []):
            calculated = expected.get(bar['t'])
            findings['reconciliation'].append(dict(symbol=symbol, bar=bar, calculated=calculated,
                differences={k:float(bar[k])-calculated[k] for k in ('o','h','l','c','v','n','vw')}
                if calculated and all(calculated[k] is not None for k in ('o','h','l','c','v','n','vw')) else {}))
    findings['feed_controls'] = []
    for feed in ('opra', 'indicative', 'etfe-invalid-feed-control'):
        control = pages(client, 'option_trades', dict(params, feed=feed), 'trades', max_pages=1)
        findings['feed_controls'].append(dict(feed=feed, complete=control['complete'],
            receipts=control['receipts'], same_as_no_feed=control['records']==large['records']))
    first = large['records'].get(CONTRACTS[0], [{}])[0].get('t')
    if first:
        findings['exact_timestamp'] = pages(client, 'option_trades',
            dict(symbols=CONTRACTS[0],start=first,end=first,limit=10000,sort='asc'), 'trades', max_pages=1)
    print(json.dumps(dict(phase='trade_controls', requests=len(client.receipts))), flush=True)
    findings['metadata_cohorts'] = []
    for expiry, status in (('2023-12-15','inactive'),('2024-06-21','inactive'),
                           ('2025-01-17','inactive'),('2026-10-09','active')):
        for ticker in ('SPY','QQQ','VOO'):
            receipt, body = client.get('contracts',dict(underlying_symbols=ticker,status=status,
                expiration_date=expiry,type='call',show_deliverables='true',limit=3))
            rows = (body or {}).get('option_contracts', [])
            findings['metadata_cohorts'].append(dict(ticker=ticker,expiry=expiry,status=status,
                receipt=len(client.receipts)-1,status_code=receipt['status_code'],
                next_page_available=bool((body or {}).get('next_page_token')),rows=rows))
            if expiry=='2023-12-15' and rows:
                symbol=rows[0]['symbol']
                findings.setdefault('older_expiry_samples',[]).append(dict(symbol=symbol,
                    result=pages(client,'option_bars',dict(symbols=symbol,timeframe='1Min',
                        start='2020-01-01T00:00:00Z',end='2023-12-16T00:00:00Z',
                        limit=1,sort='asc'),'bars',max_pages=1)))
    result=dict(schema='etfe-alpaca-pull-diagnosis-v1',
        observed_at=datetime.now(timezone.utc).isoformat(),setup_plan_sha256=setup['plan_sha256'],
        requests=len(client.receipts),source_bindings={n:file_sha(ROOT/n) for n in (
            'scripts/diagnose_etfe_alpaca_pulls.py','nn_meta/etfe/alpaca_probe.py')},
        findings=findings,transport_failures=sum(bool(r['transport_error']) for r in client.receipts),
        http_status_counts=dict(Counter(str(r['status_code']) for r in client.receipts)),
        provider_global_start_verified=False,ready_for_build=False,
        receipt_files={p.name:file_sha(p) for p in sorted(output.iterdir()) if p.is_file()})
    save_new(output/'REPORT.json',result)
    print(json.dumps({k:result[k] for k in ('requests','transport_failures','http_status_counts')},indent=2))


def followup(client, setup):
    """Targeted successor; do not repeat successful first-pass controls."""
    baseline_path = ROOT/'nn_meta/validation/etfe-alpaca-pulls-20261003-r1/REPORT.json'
    baseline = json.loads(baseline_path.read_text())
    findings = {}
    small = pages(client, 'option_trades', dict(symbols=','.join(CONTRACTS),
        start='2024-01-18T14:30:00Z', end='2024-01-18T14:30:59.999999999Z',
        sort='asc', limit=2), 'trades')
    findings['pagination'] = dict(small,
        same_occurrences=small['records']==baseline['findings']['large_page']['records'])
    if not small['complete']:
        save_new(client.output/'PARTIAL.json', findings)
        raise SystemExit('Pagination control incomplete; stopped before dependent controls')
    findings['metadata_cohorts'] = []
    for ticker in ('SPY', 'QQQ', 'VOO'):
        for bounds in (dict(expiration_date_gte='2020-01-01', expiration_date_lte='2024-01-17'),
                       dict(expiration_date='2024-02-16'), dict(expiration_date='2024-03-15')):
            receipt, body = client.get('contracts', dict(underlying_symbols=ticker,
                status='inactive', type='call', show_deliverables='true', limit=3, **bounds))
            findings['metadata_cohorts'].append(dict(ticker=ticker, bounds=bounds,
                receipt=len(client.receipts)-1, status_code=receipt['status_code'],
                body=body))
    findings['long_dated_pre_floor'] = []
    for cohort in baseline['findings']['metadata_cohorts']:
        if cohort['expiry'] != '2024-06-21' or not cohort['rows']:
            continue
        symbol = cohort['rows'][-1]['symbol']
        for route, field in (('option_trades','trades'), ('option_bars','bars')):
            params = dict(symbols=symbol, start='1970-01-01T00:00:00Z',
                end='2024-01-18T14:29:59.999999999Z', sort='asc', limit=1)
            if field == 'bars':
                params['timeframe'] = '1Min'
            findings['long_dated_pre_floor'].append(dict(symbol=symbol, route=route,
                result=pages(client, route, params, field, max_pages=1)))
    result = dict(schema='etfe-alpaca-pull-followup-v1',
        observed_at=datetime.now(timezone.utc).isoformat(), setup_plan_sha256=setup['plan_sha256'],
        baseline_report_sha256=file_sha(baseline_path), requests=len(client.receipts), findings=findings,
        source_bindings={n:file_sha(ROOT/n) for n in (
            'scripts/diagnose_etfe_alpaca_pulls.py','nn_meta/etfe/alpaca_probe.py')},
        transport_failures=sum(bool(r['transport_error']) for r in client.receipts),
        http_status_counts=dict(Counter(str(r['status_code']) for r in client.receipts)),
        provider_global_start_verified=False, ready_for_build=False,
        receipt_files={p.name:file_sha(p) for p in sorted(client.output.iterdir()) if p.is_file()})
    save_new(client.output/'REPORT.json', result)
    print(json.dumps({k:result[k] for k in ('requests','transport_failures','http_status_counts')},indent=2))


if __name__=='__main__':
    main()
