"""Seal one exact listed history interval between noncash boundaries."""
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
    if (review.get('schema') != 'v7-reviewed-single-noncash-epoch-v1'
            or not isinstance(ids, list) or not ids or len(ids) != len(set(ids))
            or review.get('held_position_treatment') != 'reject_crossing_position'
            or review.get('factor_inference') is not False):
        raise ValueError('Finite conservative single-epoch review required')
    panel = pd.read_parquet(args.coverage / 'coverage.parquet')
    history = pd.read_parquet(args.history / 'history.parquet',
                              columns=['security_id', 'source_date', 'stock_ticker',
                                       'source_status', 'identity_span'])
    eligible = pd.read_parquet(args.history / 'eligible_sources.parquet',
                               columns=['security_id', 'source_date', 'source_matches'])
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
        if observed.empty or observed.identity_span.nunique() != 1:
            raise ValueError('One observed security identity span required: ' + sid)
        symbols = set(selected.stock_ticker.dropna())
        relevant = [row for row in treatments if symbols.intersection(row['scoped_symbols'])]
        if not relevant:
            raise ValueError('Explicit original noncash treatments required: ' + sid)
        boundaries = []
        for treatment in relevant:
            if treatment['effective_date'] is not None:
                boundaries.append(treatment['effective_date'])
            else:
                if treatment['kind'] != 'name_changes' or len(treatment['replaces']) != 1:
                    raise ValueError('Undated boundary must be one name-change record: ' + sid)
                ref = treatment['replaces'][0]
                candidate = candidate_by_key[(ref['provider'], ref['kind'], ref['action_id'])]
                if candidate['record_sha256'] != ref['record_sha256'] or not candidate.get('process_date'):
                    raise ValueError('Provider process evidence differs: ' + sid)
                boundaries.append(candidate['process_date'])
        boundaries = sorted(set(boundaries))
        windows = []
        edges = ['', *boundaries, '9999-12-31']
        member = eligible[eligible.security_id.eq(sid)]
        if not member.source_matches.all():
            raise ValueError('Eligible source mismatch must be repaired first: ' + sid)
        for low, high in zip(edges, edges[1:]):
            raw = observed[observed.source_date.gt(low) & observed.source_date.lt(high)]
            if raw.empty:
                continue
            start, end = raw.source_date.min(), raw.source_date.max()
            nmember = int(member.source_date.between(start, end).sum())
            windows.append((nmember, len(raw), start, end, low, high, raw))
        if not windows:
            raise ValueError('No observed interval between noncash boundaries: ' + sid)
        nmember, _, start, end, low, high, raw = max(windows, key=lambda x: x[:4])
        if nmember == 0:
            raise ValueError('No eligible membership in any safe interval: ' + sid)
        listing_ids = []
        for day in (start, end):
            ticker = raw.loc[raw.source_date.eq(day), 'stock_ticker'].iloc[0]
            listing = reader.record(ticker, day)
            if (not listing or listing.get('composite_figi') != sid
                    or not listing.get('share_class_figi') or listing.get('active') is not True):
                raise ValueError('Selected interval lacks exact listed identity: ' + sid)
            listing_ids.append((ticker, identity(listing), listing['share_class_figi']))
        if listing_ids[0][2] != listing_ids[1][2]:
            raise ValueError('Selected interval changes share class: ' + sid)
        index = panel.security_id.eq(sid) & panel.source_date.between(start, end)
        original = panel.loc[index].copy()
        if (original.history_admitted.any()
                or not original.coverage_status.isin(
                    ['explicit_noncash_boundary_exclusion', 'unresolved_identity']).all()
                or original.unresolved_record_ids.map(bool).any()):
            raise ValueError('Unexpected existing interval admission or unresolved action: ' + sid)
        admitted = index & panel.coverage_status.eq('explicit_noncash_boundary_exclusion')
        panel.loc[admitted, 'history_admitted'] = True
        panel.loc[admitted, 'coverage_status'] = panel.loc[admitted, 'event_id'].map(
            lambda event: 'compiled_event_with_assumed_coverage' if pd.notna(event)
            else 'assumed_no_event')
        if not set(raw.source_date).issubset(set(panel.loc[admitted, 'source_date'])):
            raise ValueError('Selected raw interval omitted observed sessions: ' + sid)
        proofs.append(dict(security_id=sid, start=start, end=end,
                           previous_boundary=low or None, next_boundary=high if high != '9999-12-31' else None,
                           eligible_days=nmember, observed_days=len(raw),
                           first_listing=listing_ids[0], last_listing=listing_ids[1],
                           treatment_ids=sorted(row['review_identity'] for row in relevant),
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
        raise ValueError('Single-epoch source changed')
    with transaction(args.output) as temp:
        panel.to_parquet(temp / 'coverage.parquet', index=False)
        (temp / 'policy.json').write_bytes((args.coverage / 'policy.json').read_bytes())
        (temp / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
        (temp / 'reviews.json').write_text(json.dumps(proofs, indent=2) + '\n')
        (temp / 'report.json').write_text(json.dumps(dict(
            schema='v7-reviewed-single-noncash-epoch-v1', reviewed_securities=len(proofs),
            observed_days=sum(p['observed_days'] for p in proofs),
            eligible_days=sum(p['eligible_days'] for p in proofs),
            held_position_admitted=False, research_ready=False), indent=2) + '\n')
        if any(sha(path) != digest for path, digest in inputs.items()):
            raise ValueError('Single-epoch source changed during sealing')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(dict(reviewed_securities=len(proofs),
                          observed_days=sum(p['observed_days'] for p in proofs),
                          eligible_days=sum(p['eligible_days'] for p in proofs))))


if __name__ == '__main__':
    main()
