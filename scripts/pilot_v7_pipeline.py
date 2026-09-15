"""All-variant proposals and a fixed family/timeframe full-row/quote-label pilot."""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_one(payload):
    args, minutes = payload
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import time
    import resource
    import pandas as pd
    import polars as pl
    from nn_meta.v7.bars import aggregate_lazy
    from nn_meta.v7.context import chart_context
    from nn_meta.v7.features import source_frames, project, technical
    from nn_meta.v7.proposals import proposal_batches
    from nn_meta.v7.rows import FeatureRows, schema
    from nn_meta.v7.coverage import receipt_frame
    from nn_meta.v7.storage import transaction, receipt, verify
    from nn_meta.v7.provenance import RunBinding
    from nn_meta.v7.chain import ObservedChain
    from nn_meta.v7.contracts import ContractReferences
    from nn_meta.v7.quote_archive import QuoteArchive
    from nn_meta.v7.tick_features import features as tick_features
    from nn_meta.v7.replay import replay
    from nn_meta.v7.execution import CaptureUnavailable
    from nn_meta.multitimeframe_catalog import registered_catalog
    from nn_meta.session_calendar import SessionCalendar
    from nn_meta.option_tick_dataset import feature_policy
    from options.data.provider import parse_occ_symbol
    start, end = '2022-03-07', '2022-03-11'
    began = time.perf_counter()
    paths = {name: Path(value) for name, value in args.items()}
    calendar_path = paths['source'] / 'calendar.json'
    calendar_doc = json.loads(calendar_path.read_text())
    calendar = SessionCalendar(calendar_doc)
    variants = [r for r in registered_catalog(['SPY'])['records'] if r['signal_minutes'] == minutes]
    declaration = {'symbol': 'SPY', 'signal_minutes': minutes, 'start': start, 'end': end,
                   'target_dte': 1, 'variants': variants,
                   'sample_rule': 'earliest (decision_ns, variant_id, proposal_id) per family; no outcome filter',
                   'close_extension_minutes': 15, 'liquidation_before_close_minutes': 15,
                   'dated_session_policy_verified': False, 'price_vintage_verified': False,
                   'research_ready': False}
    stock_receipts = [paths['source'] / f'stock_1m/{b}/SPY/{y}/complete.json'
                      for b in ('raw', 'all') for y in (2021, 2022)]
    tick_reference = ROOT / 'docs/reviews/2026-09-06-option-condition-209.json'
    inputs = [calendar_path, *stock_receipts, paths['daily'] / 'complete.json',
              paths['chain'].parent / 'complete.json', paths['quotes'] / 'requests.json',
              tick_reference, ROOT / 'docs/specs/V7_EVALUATION_20260915.json']
    # The per-capture and metadata receipts are verified when read; include
    # their full immutable inventory so the run guards them too.
    inputs += sorted(paths['quotes'].glob('*/complete.json'))
    inputs += sorted(paths['references'].glob('*/*/complete.json'))
    binding = RunBinding(ROOT, inputs=inputs, declaration=declaration)
    stock = {'raw': [], 'all': []}
    for path in stock_receipts:
        doc, frame = receipt_frame(paths['source'], path)
        del frame
        stock[doc['task']['adjustment']].extend(path.parent / n for n in doc['files'] if n.endswith('bars.parquet'))
    stop = pd.Timestamp(end, tz='America/New_York') + pd.DateOffset(days=1)
    def bars_at(basis, m):
        return aggregate_lazy(stock[basis], calendar_doc, m).filter(
            pl.col('timestamp').cast(pl.Int64) < stop.value).collect(engine='streaming').to_pandas().set_index('timestamp')
    minute = bars_at('all', 1)
    bars = minute if minutes == 1 else bars_at('all', minutes)
    raw = bars_at('raw', 1)
    raw_series = raw.set_index('available_at').Close
    context = chart_context(bars, minute, calendar_doc, minutes)
    observed = bars.index[bars.index >= pd.Timestamp(start, tz='America/New_York')]
    frames = source_frames(bars, context, observation_index=observed)
    projected = project(bars, frames, context)
    tech = technical(bars, context)
    verify(paths['daily'])
    daily = pd.read_parquet(paths['daily'] / 'daily.parquet')
    rows = FeatureRows(bars, context, tech, projected, daily, symbol='SPY',
                       security_id='BBG000BDTBL9', sector='idx_etf')
    verify(paths['chain'].parent)
    chain = ObservedChain(paths['chain'], 'SPY')
    archive = QuoteArchive(paths['quotes'])
    references = ContractReferences(paths['references'])
    tick_policy = feature_policy(allowed_trade_conditions=[209], condition_reference_paths=[tick_reference],
        condition_policy_id='massive-options-auto-209-reference-20260906-research-only')
    def select(clock, right):
        t = pd.Timestamp(clock, unit='ns', tz='UTC')
        pos = raw_series.index.searchsorted(t, side='right') - 1
        if pos < 0 or clock - raw_series.index[pos].value > 60_000_000_000:
            return None
        value = chain.select(t.tz_convert('America/New_York').date(), float(raw_series.iloc[pos]), right, 1)
        return None if value is None else value['ticker'].removeprefix('O:')
    def cutoff(contract):
        expiry = parse_occ_symbol(contract)[1].isoformat()
        calendar.bounds(expiry)
        day = max(d for d in calendar.sessions if d <= expiry)
        return calendar.bounds(day)[1].tz_localize('UTC').value
    def close(clock):
        day = pd.Timestamp(clock, unit='ns', tz='UTC').tz_convert('America/New_York').date().isoformat()
        return (calendar.bounds(day)[1].tz_localize('UTC') + pd.Timedelta(minutes=15)).value
    clocks = [t.value for d, (opening, closing) in sorted(calendar.sessions.items()) if start <= d <= end
              for t in pd.date_range(opening.tz_localize('UTC') + pd.Timedelta(minutes=1),
                  closing.tz_localize('UTC') + pd.Timedelta(minutes=15), freq='min')]
    by_id = {r['variant_id']: r for r in variants}
    selected, count, censored, covered = {}, 0, 0, 0
    destination = paths['output'] / str(minutes)
    with transaction(destination) as temp:
        with (temp / 'proposals.jsonl').open('w') as stream:
            for records, proposals in proposal_batches('SPY', bars, variants, start=start, end=end,
                                                        sources=frames, batch_columns=16):
                covered += len(records)
                for p in proposals:
                    serial = {k: (None if pd.isna(v) else v.isoformat()) if isinstance(v, (pd.Timestamp, type(pd.NaT))) else v
                              for k, v in p.items()}
                    serial['exit_decision_ns'] = p['exit_decision_at'].value if p['proposal_closed'] else None
                    stream.write(json.dumps(serial) + '\n')
                    count += 1
                    censored += not p['proposal_closed']
                    order = (p['decision_ns'], p['variant_id'], p['proposal_id'])
                    old = selected.get(p['strategy'])
                    if old is None or order < (old['decision_ns'], old['variant_id'], old['proposal_id']):
                        selected[p['strategy']] = serial
        samples, model_rows = [], []
        for family, p in sorted(selected.items()):
            contract = select(p['decision_ns'], p['right'])
            record = {'strategy': family, 'proposal': p, 'contract': contract}
            if contract is None:
                record['status'] = 'no_prior_observed_contract'
                samples.append(record)
                continue
            decision = pd.Timestamp(p['decision_ns'], unit='ns', tz='UTC')
            day = decision.tz_convert('America/New_York').date().isoformat()
            try:
                ticks, evidence = tick_features(archive, references, symbol='SPY', contract=contract,
                    decision_ns=p['decision_ns'], minutes=minutes,
                    session_open_ns=calendar.bounds(day)[0].tz_localize('UTC').value, policy=tick_policy)
                row = rows.row(variant=by_id[p['variant_id']], bar_at=decision-pd.Timedelta(minutes=minutes),
                               right=p['right'], target_dte=1,
                               bars_since_previous_signal=p['bars_since_previous_signal'], ticks=ticks)
                row.name = p['proposal_id']
                model_rows.append(row)
                record.update(feature_lineage=row.attrs, tick_evidence=evidence)
                result = replay(p, clocks, archive, references,
                    select_contract=lambda t: select(t, p['right']), expiry_cutoff=cutoff, session_close=close)
                record.update(status='replayed', replay=result)
            except CaptureUnavailable as exc:
                record.update(status='capture_incomplete', error=str(exc))
            samples.append(record)
        pd.DataFrame(model_rows, columns=schema()).to_parquet(temp / 'feature_rows.parquet')
        (temp / 'samples.json').write_text(json.dumps(samples, indent=2) + '\n')
        report = {'minutes': minutes, 'variants': covered, 'families': len({v['strategy'] for v in variants}),
                  'proposals': count, 'censored_proposals': censored, 'sampled_families': len(samples),
                  'feature_rows': len(model_rows), 'feature_columns': len(schema()),
                  'complete_sample_labels': sum(s.get('replay', {}).get('label_complete', False) for s in samples),
                  'sample_statuses': {s['strategy']: s.get('replay', {}).get('status', s['status']) for s in samples},
                  'seconds': time.perf_counter() - began,
                  'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  'research_ready': False, 'scope': 'representative plumbing; not a full dataset or edge evaluation'}
        manifest = binding.finish()
        (temp / 'binding.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (temp / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        receipt(temp, {'identity': manifest['identity'], 'research_ready': False})
    return report


def main():
    from nn_meta.v7.runtime import worker_pool
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'daily', 'chain', 'quotes', 'references', 'output'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--workers', type=int, required=True)
    args = vars(ap.parse_args())
    workers = args.pop('workers')
    args['output'].mkdir(parents=True, exist_ok=False)
    with worker_pool(workers, threads=1) as pool:
        reports = list(pool.map(run_one, [(args, m) for m in (1, 5, 15, 30)]))
    (args['output'] / 'report.json').write_text(json.dumps(reports, indent=2) + '\n')
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    main()
