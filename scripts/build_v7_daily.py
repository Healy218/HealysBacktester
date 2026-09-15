"""Build a receipt-backed daily-context pilot for the market reference security."""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    import pyarrow.parquet as pq
    from dataclasses import asdict
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.daily import surface_day, daily_context, SurfacePolicy
    from nn_meta.v7.coverage import audit_pair
    from nn_meta.v7.provenance import RunBinding
    from nn_meta.v7.storage import verify, receipt, transaction, sha
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'audit', 'reference', 'output'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--end', required=True)
    args = ap.parse_args()
    calendar_path = args.source / 'calendar.json'
    calendar_doc = json.loads(calendar_path.read_text())
    calendar = SessionCalendar(calendar_doc)
    reference_receipt = verify(args.reference)
    query = reference_receipt['query']
    if query['path'] != '/v3/reference/tickers/SPY' or query['params']['date'] > args.end:
        raise ValueError('Dated SPY reference required')
    reference = json.loads((args.reference / 'response.json').read_text())['results']
    security_id = reference['composite_figi']
    if reference['ticker'] != 'SPY' or not security_id:
        raise ValueError('SPY identity required')
    days = sorted(d for d in calendar.sessions if '2021-01-01' <= d <= args.end)
    option_inputs = [args.audit / 'options' / d / 'complete.json' for d in days]
    stock_inputs = [args.source / f'stock_1m/{b}/SPY/{y}/complete.json'
                    for y in range(2021, int(args.end[:4]) + 1) for b in ('raw', 'all')]
    policy = SurfacePolicy()
    declaration = {'symbol': 'SPY', 'security_id': security_id, 'end': args.end,
                   'surface_policy': asdict(policy), 'availability': 'next regular session open',
                   'price_vintage_verified': False, 'research_ready': False}
    binding = RunBinding(ROOT, inputs=[calendar_path, args.reference / 'complete.json',
                                     *option_inputs, *stock_inputs], declaration=declaration)
    frames = []
    for year in range(2021, int(args.end[:4]) + 1):
        summary, _, daily = audit_pair(args.source, 'SPY', year, calendar_doc)
        if not summary['timestamp_parity']:
            raise ValueError('Stock raw/adjusted timelines differ')
        frames.append(daily)
    stock = pd.concat(frames).pivot(index='date', columns='basis', values='Close')
    stock = stock.rename(columns={'raw': 'raw_close', 'all': 'adjusted_close'})
    stock = stock.loc[stock.index <= args.end].reset_index().rename(columns={'date': 'source_date'})
    prices = stock.set_index('source_date').raw_close
    surfaces = []
    with transaction(args.output) as temp:
        for day in days:
            path = args.audit / 'options' / day
            doc = verify(path)
            if doc.get('kind') != 'options' or doc.get('key') != day:
                raise ValueError('Daily option audit scope mismatch')
            # Follow the audit back to its original acquisition receipt.
            raw_receipt = args.source / f'options/day_aggs/{day}/complete.json'
            summary = json.loads((path / 'summary.json').read_text())
            if sha(raw_receipt) != summary['input_receipt_sha256']:
                raise ValueError('Daily aggregate lineage mismatch')
            options = pq.read_table(path / 'contracts.parquet', columns=['ticker', 'close', 'volume']).to_pandas()
            surfaces.append(surface_day('SPY', day, options, prices.loc[day], policy=policy))
        surface = pd.DataFrame(surfaces)
        daily = daily_context(stock, surface, calendar, security_id=security_id, is_market=True)
        surface.to_parquet(temp / 'surfaces.parquet', index=False)
        daily.to_parquet(temp / 'daily.parquet')
        manifest = binding.finish()
        (temp / 'binding.json').write_text(json.dumps(manifest, indent=2) + '\n')
        report = {**declaration, 'days': len(daily), 'daily_columns': list(daily.columns),
                  'last_source_date': daily.source_date.iloc[-1],
                  'last_available_at': daily.index[-1].isoformat()}
        (temp / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        receipt(temp, {'identity': manifest['identity'], 'research_ready': False})
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
