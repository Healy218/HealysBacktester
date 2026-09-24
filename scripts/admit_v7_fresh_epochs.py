"""Seal exact raw postevent epochs for reviewed dated noncash boundaries."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify

    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('history', 'coverage', 'noncash', 'reviews', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / 'nn_meta'):
        raise ValueError('Repository artifact disk required')
    for path in (args.history, args.coverage, args.noncash):
        verify(path)
    review = json.loads(args.reviews.read_text())
    ids = review.get('security_ids')
    if (review.get('schema') != 'v7-reviewed-post-noncash-epochs-v1'
            or not isinstance(ids, list) or not ids or len(ids) != len(set(ids))
            or review.get('held_position_treatment') != 'reject_crossing_position'
            or review.get('factor_inference') is not False
            or review.get('successor_identity_inference') is not False):
        raise ValueError('Finite conservative fresh-epoch review required')
    panel = pd.read_parquet(args.coverage / 'coverage.parquet')
    history = pd.read_parquet(args.history / 'history.parquet',
                              columns=['security_id', 'source_date', 'stock_ticker', 'source_status'])
    if (panel.duplicated(['security_id', 'source_date']).any()
            or history.duplicated(['security_id', 'source_date']).any()
            or set(ids) - set(history.security_id)):
        raise ValueError('Unique complete history and reviewed IDs required')
    treatments = json.loads((args.noncash / 'treatments.json').read_text())
    proofs = []
    for sid in ids:
        selected = history[history.security_id.eq(sid)]
        symbols = set(selected.stock_ticker.dropna())
        relevant = [row for row in treatments if symbols.intersection(row['scoped_symbols'])]
        if (not relevant or any(not row.get('effective_date') for row in relevant)
                or any(row.get('treatment') != 'explicit_boundary_exclusion' for row in relevant)):
            raise ValueError('Every scoped noncash treatment must have a dated boundary')
        last = max(row['effective_date'] for row in relevant)
        index = panel.security_id.eq(sid) & panel.source_date.gt(last)
        dates = set(selected.loc[selected.source_date.gt(last)
                                 & selected.source_status.eq('observed'), 'source_date'])
        if not dates:
            raise ValueError('No postboundary observed raw session')
        original = panel.loc[index].copy()
        if (original.history_admitted.any()
                or not original.coverage_status.isin(
                    ['explicit_noncash_boundary_exclusion', 'unresolved_identity']).all()
                or original.unresolved_record_ids.map(bool).any()):
            raise ValueError('Unexpected preexisting postboundary admission or unresolved action')
        selected_index = index & panel.coverage_status.eq('explicit_noncash_boundary_exclusion')
        panel.loc[selected_index, 'history_admitted'] = True
        panel.loc[selected_index, 'coverage_status'] = panel.loc[selected_index, 'event_id'].map(
            lambda event: 'compiled_event_with_assumed_coverage' if pd.notna(event)
            else 'assumed_no_event')
        # Keep treatment identifiers visible as provenance even on the fresh
        # epoch. Their former blocking meaning is replaced by this exact rule.
        admitted = set(panel.loc[selected_index & panel.history_admitted, 'source_date'])
        if not dates.issubset(admitted):
            raise ValueError('Fresh epoch omitted observed raw days')
        proofs.append(dict(security_id=sid, boundary=last,
                           treatment_ids=sorted(row['review_identity'] for row in relevant),
                           admitted_observed_days=len(dates),
                           first_admitted_observed=min(dates),
                           held_position_treatment='reject_crossing_position'))
    inputs = json.loads((args.coverage / 'inputs.json').read_text())
    for path in (args.coverage, args.history, args.noncash):
        doc = verify(path)
        inputs[str(path / 'complete.json')] = sha(path / 'complete.json')
        inputs.update({str(path / name): digest for name, digest in doc['files'].items()})
    inputs[str(args.reviews)] = sha(args.reviews)
    inputs[str(Path(__file__))] = sha(__file__)
    if any(sha(path) != digest for path, digest in inputs.items()):
        raise ValueError('Fresh-epoch source changed')
    with transaction(args.output) as temp:
        panel.to_parquet(temp / 'coverage.parquet', index=False)
        (temp / 'policy.json').write_bytes((args.coverage / 'policy.json').read_bytes())
        (temp / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
        (temp / 'reviews.json').write_text(json.dumps(proofs, indent=2) + '\n')
        (temp / 'report.json').write_text(json.dumps(dict(
            schema='v7-reviewed-post-noncash-epochs-v1', reviewed_securities=len(proofs),
            admitted_observed_days=sum(p['admitted_observed_days'] for p in proofs),
            held_position_admitted=False, research_ready=False), indent=2) + '\n')
        if any(sha(path) != digest for path, digest in inputs.items()):
            raise ValueError('Fresh-epoch source changed during sealing')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(dict(reviewed_securities=len(proofs),
                          admitted_observed_days=sum(p['admitted_observed_days'] for p in proofs))))


if __name__ == '__main__':
    main()
