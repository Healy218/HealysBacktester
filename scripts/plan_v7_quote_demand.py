"""Bounded full-history quote-request superset inventory; downloads no quotes."""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def work(payload):
    args, symbol = payload
    import bisect
    import re
    import resource
    import time
    import pandas as pd
    import polars as pl
    import pyarrow as pa
    import pyarrow.parquet as pq
    from nn_meta.v7.bars import aggregate_lazy
    from nn_meta.v7.chain import ObservedChain
    from nn_meta.v7.coverage import receipt_frame
    from nn_meta.v7.storage import transaction, receipt, verify, identity, sha
    began = time.perf_counter()
    calendar_path = Path(args['base']) / 'calendar.json'
    calendar = json.loads(calendar_path.read_text())
    symbol = 'BRK.B' if symbol == 'BRKB' else symbol
    if not re.fullmatch(r'[A-Z][A-Z0-9.]*', symbol):
        raise ValueError('Invalid stock symbol')
    source_files, stock_inputs = [], {}
    for year in range(int(args['start'][:4]), int(args['end'][:4]) + 1):
        chosen = Path(args['base']) / f'stock_1m/raw/{symbol}/{year}/complete.json'
        if not chosen.exists():
            raise ValueError(f'{symbol}/{year}: missing consolidated active stock source')
        stock_inputs[str(chosen)] = sha(chosen)
        source_files.append(chosen)
    code_paths = [Path(__file__), ROOT/'nn_meta/v7/chain.py', ROOT/'nn_meta/v7/bars.py', ROOT/'nn_meta/v7/coverage.py']
    sources = {str(p.relative_to(ROOT)): sha(p) for p in code_paths}
    declaration = {'symbol': symbol, 'start': args['start'], 'end': args['end'],
                   'targets': [1, 2, 4, 5, 7], 'rights': ['C', 'P'],
                   'stock_receipts': stock_inputs, 'calendar': sha(calendar_path),
                   'chain_receipt': sha(Path(args['chain']).parent/'complete.json'),
                   'sources': sources, 'close_extension_minutes': args['close_extension_minutes'],
                   'scope': 'every observed regular stock minute, all candidate-name history; conservative superset',
                   'pit_membership_filtered': False, 'dated_option_hours_verified': False}
    fingerprint = identity(declaration)
    output = Path(args['output']) / symbol
    if output.exists():
        verify(output, expected_identity=fingerprint)
        return json.loads((output/'report.json').read_text())
    bars_files = []
    for chosen in source_files:
        # The receipt validator also checks all raw pages and the stored bars.
        source_root = chosen.parents[4]
        doc, frame = receipt_frame(source_root, chosen)
        del frame
        bars_files.extend(chosen.parent/n for n in doc['files'] if n.endswith('bars.parquet'))
    begin = pd.Timestamp(args['start'], tz='America/New_York')
    stop = pd.Timestamp(args['end'], tz='America/New_York') + pd.DateOffset(days=1)
    raw = aggregate_lazy(bars_files, calendar, 1).filter(
        (pl.col('timestamp').cast(pl.Int64) >= begin.value) & (pl.col('timestamp').cast(pl.Int64) < stop.value)
    ).select('available_at', 'Close').collect(engine='streaming').to_pandas()
    raw['day'] = raw.available_at.dt.tz_convert('America/New_York').dt.date
    chain = ObservedChain(args['chain'], symbol)
    held, selected, rejected = {}, 0, 0
    for day, block in raw.groupby('day', sort=True):
        spots = block.Close.to_numpy()
        for right in ('C', 'P'):
            for target in (1, 2, 4, 5, 7):
                contracts = chain.select_many(day, spots, right, target)
                for row in contracts:
                    if row is None:
                        rejected += 1
                    else:
                        selected += 1
                        contract = row['ticker'].removeprefix('O:')
                        held.setdefault(contract, (day.isoformat(), row['expiry'].isoformat()))
    session_bounds = []
    for session in calendar['sessions']:
        day = session['date']
        if args['start'] <= day <= args['end']:
            opening = pd.Timestamp(day+' '+session['open'], tz='America/New_York')
            closing = pd.Timestamp(day+' '+session['close'], tz='America/New_York') + pd.Timedelta(minutes=args['close_extension_minutes'])
            session_bounds.append((day, opening.value, closing.value))
    session_days = [row[0] for row in session_bounds]
    schema = pa.schema([('contract', pa.string()), ('date', pa.string()),
                        ('start_ns', pa.int64()), ('end_ns', pa.int64())])
    contract_days, seconds = 0, 0
    with transaction(output) as temp:
        batch = []
        with pq.ParquetWriter(temp/'contract_days.parquet', schema, compression='zstd') as writer:
            for contract, (first_day, expiry) in sorted(held.items()):
                first = bisect.bisect_left(session_days, first_day)
                last = bisect.bisect_right(session_days, expiry)
                for day, opening, closing in session_bounds[first:last]:
                    batch.append({'contract': contract, 'date': day, 'start_ns': opening, 'end_ns': closing})
                    contract_days += 1
                    seconds += (closing-opening)//1_000_000_000
                if len(batch) >= 65536:
                    writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                    batch = []
            if batch:
                writer.write_table(pa.Table.from_pylist(batch, schema=schema))
        report = {'symbol': symbol, 'observed_stock_minutes': len(raw), 'contracts': len(held),
                  'contract_days': contract_days, 'quote_hours': seconds/3600,
                  'trade_hours': seconds/3600, 'selector_events': selected, 'no_contract_events': rejected,
                  'seconds': time.perf_counter()-began,
                  'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  'research_ready': False, 'scope': declaration['scope']}
        if {str(p.relative_to(ROOT)): sha(p) for p in code_paths} != sources:
            raise ValueError('Demand-planning source changed during the run')
        (temp/'declaration.json').write_text(json.dumps(declaration, indent=2)+'\n')
        (temp/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        receipt(temp, {'identity': fingerprint, 'research_ready': False})
    return report


def main():
    from nn_meta.v7.runtime import worker_pool
    from nn_meta.v7.storage import verify, sha
    from scripts.download_v7_data import save
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'chain', 'symbols', 'output'):
        ap.add_argument('--'+name, type=Path, required=True)
    for name in ('start', 'end'):
        ap.add_argument('--'+name, required=True)
    ap.add_argument('--close-extension-minutes', type=int, choices=[0,15], required=True)
    ap.add_argument('--workers', type=int, required=True)
    args = vars(ap.parse_args())
    from nn_meta.v7.scope import require_active_inputs, require_research_window
    require_active_inputs(args['base'])
    require_research_window(args['start'], args['end'])
    from datetime import date
    calendar = json.loads((args['base']/'calendar.json').read_text())
    if (date.fromisoformat(args['start']).isoformat() != args['start']
            or date.fromisoformat(args['end']).isoformat() != args['end']
            or not calendar['coverage_start'] <= args['start'] <= args['end'] <= calendar['coverage_end']):
        raise ValueError('Demand scope must lie within the captured calendar')
    verify(args['chain'].parent)
    chain_hash = sha(args['chain'].parent/'complete.json')
    symbols = sorted(set(args['symbols'].read_text().split()))
    reports = []
    with worker_pool(args['workers'], threads=1) as pool:
        for report in pool.map(work, [(args,symbol) for symbol in symbols]):
            reports.append(report)
            status = {'completed_symbols': len(reports), 'total_symbols': len(symbols),
                      'contract_days': sum(r['contract_days'] for r in reports),
                      'quote_hours': sum(r['quote_hours'] for r in reports), 'research_ready': False}
            save(args['output']/'status.json', status)
            print(json.dumps(status), flush=True)
    verify(args['chain'].parent)
    if sha(args['chain'].parent/'complete.json') != chain_hash:
        raise ValueError('Chain receipt changed during the run')
    save(args['output']/'report.json', reports)


if __name__ == '__main__':
    main()
