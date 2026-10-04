"""Prepare, run, resume and audit isolated ETFE Alpaca downloads."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
from nn_meta.etfe.acquisition import SYMBOLS, audit, capture, HTTP, iter_records, job, load_plan, prepare


def interval(start, end):
    """Civil New York dates → explicit half-open UTC → inclusive provider end."""
    a = pd.Timestamp(start, tz='America/New_York').tz_convert('UTC')
    b = pd.Timestamp(end, tz='America/New_York').tz_convert('UTC')-pd.Timedelta(1, 'ns')
    return dict(start=a.isoformat(), end=b.isoformat())


def bootstrap_jobs():
    jobs = []
    for ticker in SYMBOLS:
        for start, end in [('2024-01-01','2024-02-01'), ('2026-10-01','2026-10-03')]:
            jobs.append(job('stock_bars', dict(symbols=ticker, timeframe='1Min', feed='sip',
                adjustment='raw', asof='-', sort='asc', limit=10000, **interval(start,end)),
                f'fresh_stock:{ticker}:{start}'))
        for expiry in ('2024-01-19', '2026-10-02'):
            for status in ('active', 'inactive'):
                jobs.append(job('contracts', dict(underlying_symbols=ticker, status=status,
                    expiration_date=expiry, show_deliverables='true', limit=1000),
                    f'fresh_symbol_discovery:{ticker}:{expiry}:{status}'))
    return jobs


def option_jobs(parent):
    """Transport sample from fresh downloads, never a historical eligible chain."""
    plan = load_plan(parent)
    if not audit(parent)['capture_complete']:
        raise ValueError('Finish fresh stock/discovery capture before selecting transport samples')
    jobs, selections = [], []
    for ticker in SYMBOLS:
        for day, expiry in [('2024-01-18','2024-01-19'), ('2026-10-02','2026-10-02')]:
            opened = pd.Timestamp(day+' 09:30', tz='America/New_York').tz_convert('UTC')
            month = '2024-01-01' if day.startswith('2024') else '2026-10-01'
            stock = next(j for j in plan['jobs'] if j['purpose'] == f'fresh_stock:{ticker}:{month}')
            opening = next((r for r in iter_records(parent, stock)
                            if pd.Timestamp(r['raw']['t']) == opened), None)
            if opening is None:
                raise ValueError(f'Missing stock opening bar for {ticker}/{day}')
            spot = Decimal(str(opening['raw']['o']))
            candidates = {}
            for item in plan['jobs']:
                if item['purpose'].startswith(f'fresh_symbol_discovery:{ticker}:{expiry}:'):
                    for r in iter_records(parent, item):
                        row = r['raw']
                        if row['symbol'] in candidates and candidates[row['symbol']]['raw'] != row:
                            raise ValueError('Conflicting fresh contract records')
                        candidates[row['symbol']] = r
            selected = []
            for right in ('call','put'):
                choices = [r for r in candidates.values() if r['raw']['type'] == right]
                if not choices:
                    raise ValueError(f'Missing {right} symbols for {ticker}/{expiry}')
                picked = min(choices, key=lambda r:(abs(Decimal(r['raw']['strike_price'])-spot),r['symbol']))
                selected.append(picked['symbol'])
                selections.append(dict(ticker=ticker, day=day, right=right, symbol=picked['symbol'],
                    stock_open_source=opening['source'], discovery_source=picked['source'],
                    use='transport_sample_only_not_strategy_selection'))
            next_day = str((pd.Timestamp(day)+pd.Timedelta(days=1)).date())
            params = dict(symbols=','.join(sorted(selected)), sort='asc', limit=10000)
            jobs.append(job('option_bars', dict(params, timeframe='1Min', **interval(day,next_day)),
                f'fresh_option_bars:{ticker}:{day}'))
            jobs.append(job('option_trades', dict(params, start=opened.isoformat(),
                end=(opened+pd.Timedelta(minutes=30)-pd.Timedelta(1,'ns')).isoformat()),
                f'fresh_option_trades:{ticker}:{day}:opening30m'))
    return jobs, dict(plan_sha256=plan['sha256'], root=str(Path(parent).resolve()), selections=selections)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare-bootstrap','prepare-options','run','audit'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--parent', type=Path)
    p.add_argument('--request-budget', type=int)
    args = p.parse_args()
    root = args.root.resolve()
    allowed = ROOT/'nn_meta/data_cache_etfe'
    if root.parent != allowed or not root.name.startswith('alpaca-fresh-'):
        p.error('Use a direct nn_meta/data_cache_etfe/alpaca-fresh-* root')
    if args.command == 'prepare-bootstrap':
        result = prepare(root, bootstrap_jobs())
        print(json.dumps(dict(root=str(root), plan_sha256=result['sha256'], jobs=len(result['jobs']))))
    elif args.command == 'prepare-options':
        if args.parent is None or args.parent.resolve().parent != allowed:
            p.error('Fresh ETFE parent required')
        jobs, parent = option_jobs(args.parent)
        result = prepare(root, jobs, parent=parent)
        print(json.dumps(dict(root=str(root), plan_sha256=result['sha256'], jobs=len(jobs))))
    elif args.command == 'audit':
        print(json.dumps(audit(root), indent=2))
    else:
        from dotenv import dotenv_values
        values = dotenv_values(ROOT/'.env')
        credentials = {role:(values.get(key),values.get(secret)) for role,key,secret in (
            ('data','ALPACA_API_KEY','ALPACA_API_SECRET'),
            ('metadata','ALPACA_PAPER_API_KEY','ALPACA_PAPER_API_SECRET'))}
        if not all(all(pair) for pair in credentials.values()):
            p.error('Missing Alpaca credential pairs')
        result = capture(root, HTTP(credentials), request_budget=args.request_budget)
        print(json.dumps({k:result[k] for k in ('capture_complete','requests_this_run','stop_reason',
            'elapsed_seconds','peak_rss_bytes','ready_for_build')}, indent=2))
        print(json.dumps(dict(partitions=len(result['partitions']),
            terminal=sum(p['terminal'] for p in result['partitions']),
            rows=sum(p['rows'] for p in result['partitions']))))
        if not result['capture_complete'] or result['stop_reason']:
            raise SystemExit(2)


if __name__ == '__main__':
    main()
