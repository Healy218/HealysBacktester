"""Seal observed old-identity history before an undated provider process."""
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
    from nn_meta.v7.listed_evidence import ListedEvidence
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify

    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('history', 'coverage', 'noncash', 'inventory', 'reviews',
                 'listed-captures', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / 'nn_meta'):
        raise ValueError('Repository artifact disk required')
    for path in (args.history, args.coverage, args.noncash, args.inventory):
        verify(path)
    review = json.loads(args.reviews.read_text())
    ids = review.get('security_ids')
    if (review.get('schema') != 'v7-reviewed-preprocess-history-v1'
            or not isinstance(ids, list) or not ids or len(ids) != len(set(ids))
            or review.get('held_position_treatment') != 'reject_crossing_position'
            or review.get('successor_identity_admitted') is not False
            or review.get('factor_inference') is not False):
        raise ValueError('Finite conservative old-identity review required')
    panel = pd.read_parquet(args.coverage / 'coverage.parquet')
    history = pd.read_parquet(args.history / 'history.parquet',
                              columns=['security_id', 'source_date', 'stock_ticker', 'source_status'])
    if (panel.duplicated(['security_id', 'source_date']).any()
            or history.duplicated(['security_id', 'source_date']).any()
            or set(ids) - set(history.security_id)):
        raise ValueError('Unique complete history and reviewed IDs required')
    treatments = json.loads((args.noncash / 'treatments.json').read_text())
    candidates = json.loads((args.inventory / 'candidates.json').read_text())
    candidate_by_key = {(r['provider'], r['kind'], r['action_id']): r for r in candidates}
    reader = ListedEvidence(args.listed_captures)
    proofs = []
    for sid in ids:
        selected = history[history.security_id.eq(sid)]
        observed = selected[selected.source_status.eq('observed')]
        if observed.empty:
            raise ValueError('Old identity needs genuine observed history')
        last = observed.source_date.max()
        ticker = observed.loc[observed.source_date.eq(last), 'stock_ticker'].iloc[0]
        listing = reader.record(ticker, last)
        if (not listing or listing.get('composite_figi') != sid
                or not listing.get('share_class_figi') or listing.get('active') is not True):
            raise ValueError('Last old-identity session lacks exact listed proof')
        symbols = set(selected.stock_ticker.dropna())
        relevant = [row for row in treatments if symbols.intersection(row['scoped_symbols'])]
        undated = [row for row in relevant if row['effective_date'] is None]
        dated = [row for row in relevant if row['effective_date'] is not None]
        if not undated or any(row['kind'] != 'name_changes' for row in undated):
            raise ValueError('Original undated name-change treatments required: ' + sid)
        process_days = []
        for treatment in undated:
            if len(treatment['replaces']) != 1:
                raise ValueError('Exact original provider record required')
            ref = treatment['replaces'][0]
            candidate = candidate_by_key[(ref['provider'], ref['kind'], ref['action_id'])]
            if (candidate['record_sha256'] != ref['record_sha256']
                    or not candidate.get('process_date')):
                raise ValueError('Bound provider process date required')
            process_days.append(candidate['process_date'])
        if min(process_days) <= last:
            raise ValueError('Old-identity observed history reaches provider process')
        last_dated = max((row['effective_date'] for row in dated
                          if row['effective_date'] <= last), default=None)
        index = panel.security_id.eq(sid) & panel.source_date.le(last)
        if last_dated:
            index &= panel.source_date.gt(last_dated)
        admissible_observed = observed[observed.source_date.gt(last_dated)] if last_dated else observed
        if admissible_observed.empty:
            raise ValueError('No old-identity raw history after dated boundaries: ' + sid)
        original = panel.loc[index].copy()
        if (original.history_admitted.any()
                or not original.coverage_status.isin(
                    ['explicit_noncash_boundary_exclusion', 'unresolved_identity']).all()
                or original.unresolved_record_ids.map(bool).any()):
            raise ValueError('Unexpected old-identity coverage or unresolved action')
        admitted = index & panel.coverage_status.eq('explicit_noncash_boundary_exclusion')
        panel.loc[admitted, 'history_admitted'] = True
        panel.loc[admitted, 'coverage_status'] = panel.loc[admitted, 'event_id'].map(
            lambda event: 'compiled_event_with_assumed_coverage' if pd.notna(event)
            else 'assumed_no_event')
        if not set(admissible_observed.source_date).issubset(set(panel.loc[admitted, 'source_date'])):
            raise ValueError('Reviewed old history omitted observed sessions')
        proofs.append(dict(security_id=sid, last_observed=last, last_ticker=ticker,
                           last_listing_identity=identity(listing), process_days=sorted(process_days),
                           last_prior_dated_boundary=last_dated,
                           treatment_ids=sorted(row['review_identity'] for row in relevant),
                           admitted_observed_days=len(admissible_observed),
                           held_position_treatment='reject_crossing_position'))
    inputs = json.loads((args.coverage / 'inputs.json').read_text())
    for path in (args.coverage, args.history, args.noncash, args.inventory):
        doc = verify(path)
        inputs[str(path / 'complete.json')] = sha(path / 'complete.json')
        inputs.update({str(path / name): digest for name, digest in doc['files'].items()})
    inputs.update(reader.inputs)
    inputs[str(args.reviews)] = sha(args.reviews)
    inputs[str(Path(__file__))] = sha(__file__)
    if any(sha(path) != digest for path, digest in inputs.items()):
        raise ValueError('Preprocess review source changed')
    with transaction(args.output) as temp:
        panel.to_parquet(temp / 'coverage.parquet', index=False)
        (temp / 'policy.json').write_bytes((args.coverage / 'policy.json').read_bytes())
        (temp / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
        (temp / 'reviews.json').write_text(json.dumps(proofs, indent=2) + '\n')
        (temp / 'report.json').write_text(json.dumps(dict(
            schema='v7-reviewed-preprocess-history-v1', reviewed_securities=len(proofs),
            admitted_observed_days=sum(p['admitted_observed_days'] for p in proofs),
            held_position_admitted=False, research_ready=False), indent=2) + '\n')
        if any(sha(path) != digest for path, digest in inputs.items()):
            raise ValueError('Preprocess review source changed during sealing')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(dict(reviewed_securities=len(proofs),
                          admitted_observed_days=sum(p['admitted_observed_days'] for p in proofs))))


if __name__ == '__main__':
    main()
