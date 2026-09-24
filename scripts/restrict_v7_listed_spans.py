"""Restrict selected histories to one exact listed identity span."""
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
    for name in ('history', 'coverage', 'reviews', 'listed-captures', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / 'nn_meta'):
        raise ValueError('Repository artifact disk required')
    for path in (args.history, args.coverage):
        verify(path)
    review = json.loads(args.reviews.read_text())
    ids = review.get('security_ids')
    if (review.get('schema') != 'v7-reviewed-single-listed-span-v1'
            or not isinstance(ids, list) or not ids or len(ids) != len(set(ids))
            or review.get('held_position_treatment') != 'reject_crossing_identity_gap'):
        raise ValueError('Finite exact listed-span review required')
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
    reader = ListedEvidence(args.listed_captures)
    proofs = []
    for sid in ids:
        selected = history[history.security_id.eq(sid)]
        observed = selected[selected.source_status.eq('observed')]
        if observed.empty or observed.identity_span.isna().any():
            raise ValueError('Exact observed listed spans required: ' + sid)
        member = eligible[eligible.security_id.eq(sid)]
        windows = []
        for span, rows in observed.groupby('identity_span'):
            start, end = rows.source_date.min(), rows.source_date.max()
            nmember = int(member.source_date.between(start, end).sum())
            windows.append((nmember, len(rows), start, end, span, rows))
        if len(windows) < 2:
            raise ValueError('At least two interrupted listed spans required: ' + sid)
        nmember, _, start, end, span, raw = max(windows, key=lambda row: row[:4])
        if nmember == 0:
            raise ValueError('No eligible days in selected exact span: ' + sid)
        listings = []
        for day in (start, end):
            ticker = raw.loc[raw.source_date.eq(day), 'stock_ticker'].iloc[0]
            listing = reader.record(ticker, day)
            if (not listing or listing.get('composite_figi') != sid
                    or not listing.get('share_class_figi') or listing.get('active') is not True):
                raise ValueError('Selected span endpoint lacks exact listing: ' + sid)
            listings.append((ticker, identity(listing), listing['share_class_figi']))
        if listings[0][2] != listings[1][2]:
            raise ValueError('Selected span changes share class: ' + sid)
        selected_dates = set(selected.loc[selected.identity_span.eq(span)
                                         & selected.source_date.between(start, end), 'source_date'])
        if not set(raw.source_date).issubset(selected_dates):
            raise ValueError('Selected span omitted raw observation: ' + sid)
        outside = panel.security_id.eq(sid) & ~panel.source_date.isin(selected_dates)
        changed = outside & panel.history_admitted.astype(bool)
        if not changed.any():
            raise ValueError('No previously admitted cross-span history: ' + sid)
        panel.loc[changed, 'history_admitted'] = False
        panel.loc[changed, 'coverage_status'] = 'excluded_unlinked_identity_span'
        # The original action/identity event IDs stay visible, but no
        # consumer can select their session outside this one bound span.
        proofs.append(dict(security_id=sid, selected_span=span, start=start, end=end,
                           eligible_days=nmember, observed_days=len(raw),
                           excluded_admitted_days=int(changed.sum()),
                           first_listing=listings[0], last_listing=listings[1],
                           held_position_treatment='reject_crossing_identity_gap'))
    inputs = json.loads((args.coverage / 'inputs.json').read_text())
    for path in (args.coverage, args.history):
        doc = verify(path)
        inputs[str(path / 'complete.json')] = sha(path / 'complete.json')
        inputs.update({str(path / name): digest for name, digest in doc['files'].items()})
    inputs.update(reader.inputs)
    inputs[str(args.reviews)] = sha(args.reviews)
    inputs[str(Path(__file__))] = sha(__file__)
    if any(sha(path) != digest for path, digest in inputs.items()):
        raise ValueError('Listed-span source changed')
    with transaction(args.output) as temp:
        panel.to_parquet(temp / 'coverage.parquet', index=False)
        (temp / 'policy.json').write_bytes((args.coverage / 'policy.json').read_bytes())
        (temp / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
        (temp / 'reviews.json').write_text(json.dumps(proofs, indent=2) + '\n')
        (temp / 'report.json').write_text(json.dumps(dict(
            schema='v7-reviewed-single-listed-span-v1', reviewed_securities=len(proofs),
            excluded_admitted_days=sum(p['excluded_admitted_days'] for p in proofs),
            held_position_admitted=False, research_ready=False), indent=2) + '\n')
        if any(sha(path) != digest for path, digest in inputs.items()):
            raise ValueError('Listed-span source changed during sealing')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(dict(reviewed_securities=len(proofs),
                          excluded_admitted_days=sum(p['excluded_admitted_days'] for p in proofs))))


if __name__ == '__main__':
    main()
