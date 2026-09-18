"""Consume named raw daily supplements using retained exact-day listed identities."""
from pathlib import Path
import argparse
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.v7.history_supplement import supplement_history
    from nn_meta.v7.listed_evidence import ListedEvidence
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('history', 'listed-captures', 'request', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--daily', type=Path, action='append', required=True)
    parser.add_argument('--security-id', required=True)
    args = parser.parse_args()
    if (not args.output.resolve().is_relative_to(ROOT / 'nn_meta')
            or shutil.disk_usage(ROOT).free < 100 * 1024**3):
        raise ValueError('Repository artifact disk and 100 GiB reserve required')
    inputs = {}

    def merge(values):
        for p, h in values.items():
            if p in inputs and inputs[p] != h: raise ValueError('Conflicting history input binding')
            inputs[p] = h

    for path in (args.history, *args.daily):
        doc = verify(path)
        merge({str(path / 'complete.json'): sha(path / 'complete.json')})
        merge({str(path / n): h for n, h in doc['files'].items()})
    merge(json.loads((args.history / 'inputs.json').read_text()))
    request = json.loads(args.request.read_text())
    if request.get('schema') != 'v7-named-missing-history-input-v1':
        raise ValueError('Named missing consumer input required')
    frames = []
    for path in args.daily:
        declaration = json.loads((path / 'declaration.json').read_text())
        if declaration['stock_ticker'] != request['symbol']:
            raise ValueError('Supplement differs from named missing ticker')
        merge(declaration['inputs']); merge(declaration['sources'])
        frame = pd.read_parquet(path / 'daily.parquet')
        if not frame.source_date.between(request['start'], request['end']).all():
            raise ValueError('Supplement exceeds named date scope')
        frames.append(frame)
    raw = pd.concat(frames, ignore_index=True)
    reader, identities = ListedEvidence(args.listed_captures), []
    for row in raw.itertuples():
        listing = reader.record(row.stock_ticker, row.source_date)
        if not listing or listing.get('composite_figi') != args.security_id:
            raise ValueError('Every supplemental date requires the exact scoped listed identity')
        identities.append(dict(stock_ticker=row.stock_ticker, source_date=row.source_date,
            listed_security_id=args.security_id, identity_status='dated_identity',
            identity_evidence_identity=identity(listing)))
    merge(reader.inputs)
    for path in [Path(__file__), args.request, *[ROOT / 'nn_meta/v7' / (n + '.py') for n in
            ('history_supplement', 'security_history', 'listed_evidence', 'daily_identities', 'action_inventory', 'storage', 'runtime')]]:
        merge({str(path): sha(path)})
    before = pd.read_parquet(args.history / 'history.parquet')
    result = supplement_history(before, raw.merge(pd.DataFrame(identities), on=['stock_ticker','source_date'],
        validate='one_to_one'), security_id=args.security_id, evidence_identity=identity(inputs))
    eligible = pd.read_parquet(args.history / 'eligible_sources.parquet')
    comparison = eligible[['security_id', 'source_date', 'stock_ticker_expected']].merge(
        result[['security_id', 'source_date', 'stock_ticker', 'source_status']],
        on=['security_id','source_date'], validate='one_to_one', how='left').rename(columns={'stock_ticker':'stock_ticker_selected'})
    comparison['source_matches'] = comparison.stock_ticker_expected.eq(comparison.stock_ticker_selected).fillna(False)
    report = dict(security_calendar_rows=len(result), securities=result.security_id.nunique(),
        sessions=result.source_date.nunique(), identity_spans=result.identity_span.nunique(),
        supplemented_sessions=len(raw), supplemented_observed_sessions=int(raw.observed_minutes.gt(0).sum()),
        source_statuses=result.source_status.value_counts().to_dict(),
        eligible_source_unresolved=int((~comparison.source_matches).sum()),
        action_adjustments_applied=False, research_ready=False)
    if any(sha(p) != h for p,h in inputs.items()): raise ValueError('Supplement source changed')
    with transaction(args.output) as temp:
        result.to_parquet(temp / 'history.parquet', index=False)
        comparison.to_parquet(temp / 'eligible_sources.parquet', index=False)
        for name, value in [('inputs', inputs), ('report', report)]:
            (temp / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
