#!/usr/bin/env python3
"""Run current retained option paths through shared funded execution.

No proposal regeneration, option replay, capture, or fitting. Sealed outputs keep
the reconciled partial ledger and exact next inputs; repeat with new receipts.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('paths', 'quotes', 'hours', 'calendar', 'settlement', 'cash-events', 'renames',
                 'boundaries', 'blackouts', 'references', 'splits', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--stock-capture', type=Path, action='append', default=[])
    parser.add_argument('--expiry-references', type=Path)
    parser.add_argument('--through', required=True, help='Explicit last valuation date')
    args = parser.parse_args()
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.v7.storage import identity, receipt, transaction, sha, verify
    from nn_meta.v7.dated_hours import DatedHours, MINUTE
    from nn_meta.v7.contract_blackouts import BlackoutReferences, BlackoutPolicy
    from nn_meta.v7.contracts import ContractReferences
    from nn_meta.v7.integrated_inputs import (
        BoundInputs, RecordingOptions, RecordingStocks, PhysicalInputs, candidates_from_discovery)
    from nn_meta.v7.integrated_portfolio import portfolio_replay
    from nn_meta.v7.packed_quote_index import IndexedQuoteArchive
    from nn_meta.v7.settlement_schedule import ReportedSettlementSchedule
    from nn_meta.v7.stock_quotes import StockQuoteArchive
    from nn_meta.session_calendar import SessionCalendar

    if not args.output.resolve().is_relative_to(ROOT/'nn_meta/validation'):
        parser.error('Use a new validation output under this repository')
    bindings = BoundInputs()
    for name in ('paths', 'quotes', 'hours', 'boundaries', 'blackouts'):
        bindings.store(getattr(args, name))
    for name in ('calendar', 'settlement', 'cash_events', 'renames', 'splits'):
        bindings.store(getattr(args, name).parent)
    for path in args.stock_capture:
        header = bindings.store(path)
        for source, digest in header['capture']['evidence'].items():
            if sha(bindings.file(source)) != digest:
                raise ValueError('Stock capture evidence changed')
    # Bind execution producers without modifying frozen original implementations.
    for name in ('integrated_inputs', 'integrated_portfolio', 'physical', 'execution',
                 'stock_quotes', 'stock_cash', 'stock_splits', 'renames', 'contracts',
                 'dated_hours', 'settlement_schedule', 'quote_archive',
                 'packed_quote_index', 'packed_quotes', 'packed_quotes_v2',
                 'noncash_admission', 'contract_blackouts', 'storage'):
        bindings.file(ROOT/'nn_meta/v7'/f'{name}.py')
    for path in (Path(__file__), ROOT/'nn_meta/session_calendar.py',
                 ROOT/'options/paper_pricing.py', ROOT/'options/paper_risk.py',
                 ROOT/'options/data/provider.py', ROOT/'options/data/massive_ticks.py'):
        bindings.file(path)
    hours = DatedHours(args.hours)
    for source, digest in hours.inputs.items():
        if sha(bindings.file(source)) != digest:
            raise ValueError('Dated hours source changed')
    blackouts = BlackoutPolicy(args.blackouts)
    for source, digest in blackouts.inputs.items():
        if sha(bindings.file(source)) != digest:
            raise ValueError('Blackout source changed')
    class References(ContractReferences):
        def standard(self, contract, day):
            value = super().standard(contract, day)
            bindings.store(self.root/contract.removeprefix('O:')/day)
            return value
    references = BlackoutReferences(References(args.references), blackouts)
    document = json.loads((args.paths/'report.json').read_text())
    candidates = candidates_from_discovery(document)
    # Exact recorded paths are the handoff; their immutable source bindings are
    # retained, not rewritten to today's source hashes or regenerated here.
    source_binding = json.loads((args.paths/'binding.json').read_text())
    bindings.file(args.paths/'binding.json')
    trading = SessionCalendar(json.loads(args.calendar.read_text()))
    settlement = ReportedSettlementSchedule(json.loads(args.settlement.read_text()), trading)
    if pd.Timestamp(args.through).date().isoformat() != args.through:
        parser.error('ISO valuation end date required')
    if args.through not in hours.calendar.sessions:
        parser.error('Valuation end must be a captured trading date')
    through = int(hours.calendar.bounds(args.through)[1].tz_localize('UTC').value)
    clocks = set()
    for candidate in candidates:
        start = candidate['decision_ns']
        end = candidate.get('pending_at_ns') or candidate['path']['label_end_ns'] or through
        if start > through or end > through:
            parser.error('Valuation horizon must include every source path/gap')
        clocks.update((start, end))
        for day in hours.days:
            if day > args.through:
                break
            if day < pd.Timestamp(start, unit='ns', tz='UTC').tz_convert('America/New_York').date().isoformat():
                continue
            session = hours.at(candidate['symbol'], day)
            lo, hi = max(start, session['open_ns']), min(end, session['close_ns']-1)
            if lo > end:
                break
            clocks.update(range(lo, hi+1, MINUTE))
        candidate['source_dates'] = [d for d in hours.days
            if start <= hours.at(candidate['symbol'], d)['close_ns'] and
            hours.at(candidate['symbol'], d)['open_ns'] <= end]
    if not clocks:
        raise ValueError('No source execution paths')
    events = json.loads(args.cash_events.read_text())
    renames = json.loads(args.renames.read_text())
    splits = [e for e in json.loads(args.splits.read_text()) if e.get('category') == 'split']
    boundaries = pd.read_parquet(args.boundaries/'coverage.parquet')
    with IndexedQuoteArchive(args.quotes) as packed:
        for path, digest in packed.db.execute('SELECT path,receipt_sha256 FROM packs'):
            bindings.store(path)
            if sha(Path(path)/'complete.json') != digest:
                raise ValueError('Packed path input changed')
        archive = RecordingOptions(packed)
        stocks = RecordingStocks(StockQuoteArchive(args.stock_capture, calendar=trading))
        physical = PhysicalInputs(settlement_calendar=settlement, stock_archive=stocks,
            hours=hours, references=references, expiry_root=args.expiry_references,
            bindings=bindings, cash_entitlements=events, renames=renames, splits=splits)
        result = portfolio_replay(candidates, sorted(clocks), archive,
                                  physical=physical, noncash_boundaries=boundaries)
    pending = {identity(r): r for r in result['pending']}
    captures = []
    for request in pending.values():
        if request['provider'] == 'massive' and request['kind'] in ('quotes', 'trades'):
            scope = {k: request[k] for k in ('contract', 'kind', 'start_ns', 'end_ns')}
            captures.append(dict(scope, request_id=identity(scope)))
    report = dict(schema='v7-integrated-execution-v1', source_paths=len(candidates),
        source_path_binding_identity=identity(source_binding),
        score_policy='constant zero; stable proposal identity order; no trained selector',
        completed_proposals=len(result['completed_proposals']),
        pending=list(pending.values()), stopped_at_ns=result['stopped_at_ns'],
        complete=result['complete'], valuation_complete=result['valuation_complete'],
        full_universe=False, research_ready=False, training_started=False,
        physical_events=sum(e.get('kind') in ('exercise', 'stock_sale', 'settlement')
                            for e in result['fills']), reconciliation=result['reconciliation'])
    binding = dict(inputs=bindings.inputs, paths=str(args.paths.resolve()),
                   quote_index=str(args.quotes.resolve()), through=args.through)
    bindings.check()
    if args.output.exists():
        verify(args.output, expected_identity=identity(binding))
    else:
        with transaction(args.output) as temporary:
            for name, value in [('binding', binding), ('report', report), ('portfolio', result),
                                ('capture-requests', captures)]:
                (temporary/f'{name}.json').write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')
            receipt(temporary, dict(identity=identity(binding), research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
