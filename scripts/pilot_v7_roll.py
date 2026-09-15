"""A fixed, preselected SPY quote/roll plumbing replay, not a strategy evaluation."""
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
    import polars as pl
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.v7.bars import aggregate_lazy
    from nn_meta.v7.chain import ObservedChain
    from nn_meta.v7.contracts import ContractReferences
    from nn_meta.v7.quote_archive import QuoteArchive
    from nn_meta.v7.replay import replay
    from nn_meta.v7.storage import transaction, receipt, identity, sha, verify
    from nn_meta.v7.coverage import receipt_frame
    from options.data.provider import parse_occ_symbol
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'chain', 'quotes', 'references', 'output'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--right', choices=['C', 'P'], required=True)
    args = ap.parse_args()
    calendar_doc = json.loads((args.source / 'calendar.json').read_text())
    calendar = SessionCalendar(calendar_doc)
    stock_receipt = args.source / 'stock_1m/raw/SPY/2022/complete.json'
    doc, frame = receipt_frame(args.source, stock_receipt)
    del frame
    paths = [stock_receipt.parent / name for name in doc['files'] if name.endswith('bars.parquet')]
    raw = aggregate_lazy(paths, calendar_doc, 1).select('available_at', 'Close').collect(engine='streaming').to_pandas()
    raw = raw.set_index('available_at').Close
    verify(args.chain.parent)
    chain = ObservedChain(args.chain, 'SPY')
    archive, references = QuoteArchive(args.quotes), ContractReferences(args.references)
    entry = pd.Timestamp('2022-03-07T14:31Z').value
    exit_at = pd.Timestamp('2022-03-10T15:00Z').value
    declaration = {'symbol': 'SPY', 'right': args.right, 'target_dte': 1,
                   'decision_ns': entry, 'exit_decision_ns': exit_at,
                   'scope': 'fixed first-minute option, target1, held through first expiry; plumbing only',
                   'close_extension_minutes': 15, 'liquidation_before_close_minutes': 15,
                   'dated_session_policy_verified': False}
    proposal = {**declaration, 'proposal_id': identity(declaration)}
    def select(clock):
        time = pd.Timestamp(clock, unit='ns', tz='UTC')
        pos = raw.index.searchsorted(time, side='right') - 1
        if pos < 0 or clock - raw.index[pos].value > 60_000_000_000:
            return None
        contract = chain.select(time.tz_convert('America/New_York').date(), float(raw.iloc[pos]), args.right, 1)
        return None if contract is None else contract['ticker'].removeprefix('O:')
    def cutoff(contract):
        expiry = parse_occ_symbol(contract)[1].isoformat()
        calendar.bounds(expiry)
        last = max(d for d in calendar.sessions if d <= expiry)
        # Declared SPY +15m class close, then -15m liquidation buffer.
        return calendar.bounds(last)[1].tz_localize('UTC').value
    def close(clock):
        day = pd.Timestamp(clock, unit='ns', tz='UTC').tz_convert('America/New_York').date().isoformat()
        return (calendar.bounds(day)[1].tz_localize('UTC') + pd.Timedelta(minutes=15)).value
    clocks = []
    for day, (opening, closing) in calendar.sessions.items():
        if '2022-03-07' <= day <= '2022-03-10':
            clocks.extend(t.value for t in pd.date_range(opening.tz_localize('UTC') + pd.Timedelta(minutes=1),
                          closing.tz_localize('UTC') + pd.Timedelta(minutes=15), freq='min') if entry <= t.value <= exit_at)
    with transaction(args.output) as temp:
        (temp / 'declaration.json').write_text(json.dumps(declaration, indent=2) + '\n')
        result = replay(proposal, clocks, archive, references, select_contract=select,
                        expiry_cutoff=cutoff, session_close=close)
        (temp / 'replay.json').write_text(json.dumps(result, indent=2) + '\n')
        receipt(temp, {'identity': identity({'declaration': declaration, 'stock': sha(stock_receipt),
                      'calendar': sha(args.source / 'calendar.json'), 'chain': sha(args.chain),
                      'quotes': sha(args.quotes / 'requests.json'),
                      'v7_sources': {p.name: sha(p) for p in (ROOT / 'nn_meta/v7').glob('*.py')},
                      'runner': sha(__file__)}), 'research_ready': False})
    print(json.dumps({k: v for k, v in result.items() if k not in ('marks', 'fills', 'attempts', 'open_positions')}, indent=2))


if __name__ == '__main__':
    main()
