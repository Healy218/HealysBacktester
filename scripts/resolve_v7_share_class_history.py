"""Apply finite reviewed share-class resolutions to the full security history."""
from pathlib import Path
import argparse
import gzip
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.v7.daily_identities import EXCHANGES, page_records, query
    from nn_meta.v7.security_history import security_history
    from nn_meta.v7.share_class_history import canonical_candidates, review_mapping
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify

    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('history', 'identities', 'listed-captures', 'stock-daily', 'reviews', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / 'nn_meta'):
        raise ValueError('Repository artifact disk required')
    if shutil.disk_usage(ROOT).free < 100 * 1024**3:
        raise ValueError('Preserve the 100 GiB disk reserve')
    inputs = {}

    def merge(values):
        for path, digest in values.items():
            if path in inputs and inputs[path] != digest:
                raise ValueError('Conflicting history source bindings')
            inputs[path] = digest

    def bind(path):
        doc = verify(path)
        merge({str(path / 'complete.json'): sha(path / 'complete.json')})
        merge({str(path / name): digest for name, digest in doc['files'].items()})
        return doc

    for path in (args.history, args.identities):
        bind(path); merge(json.loads((path / 'inputs.json').read_text()))
    bind(args.stock_daily / 'summary')
    binding = json.loads((args.stock_daily / 'summary/binding.json').read_text())
    merge(binding['declaration']['inputs']); merge(binding['declaration']['sources'])
    for path in (args.reviews, Path(__file__), *[ROOT / 'nn_meta/v7' / (n + '.py') for n in
            ('share_class_history', 'security_history', 'daily_identities', 'action_inventory', 'storage', 'runtime')]):
        merge({str(path): sha(path)})
    document = json.loads(args.reviews.read_text())
    if document.get('schema') != 'v7-reviewed-share-class-identities-v1' or not document.get('reviews'):
        raise ValueError('Explicit finite share-class reviews required')
    before = pd.read_parquet(args.history / 'history.parquet')
    if 'identity_resolution' in before:
        raise ValueError('Use the original selected history and a cumulative finite review; do not erase earlier resolutions')
    panel = pd.read_parquet(args.identities / 'identities.parquet')
    scoped_ids = set(before.security_id)
    by_key = before.set_index(['security_id', 'source_date'])
    captures = {}

    def records(day, symbol):
        if day not in captures:
            rows = []
            for exchange in EXCHANGES:
                path = args.listed_captures / day / exchange
                doc = bind(path)
                if doc['query'] != query(day, exchange):
                    raise ValueError('Dated listed capture query differs')
                seen, count = set(), 0
                for name in sorted(n for n in doc['files'] if n.startswith('page-') and n.endswith('.json.gz')):
                    page = page_records(json.loads(gzip.decompress((path / name).read_bytes())), exchange, seen)
                    rows.extend(page); count += len(page)
                if count != doc['records']:
                    raise ValueError('Dated listing count differs')
            captures[day] = rows
        matches = [r for r in captures[day] if r['ticker'] == symbol]
        if len(matches) != 1:
            raise ValueError('Unique exact-day listed record required')
        return matches[0]

    mappings = []
    for review in document['reviews']:
        symbol, sid, day = review['symbol'], review['security_id'], review['date']
        anchor = review['anchor_date']
        if (sid, anchor) not in by_key.index or (sid, day) not in by_key.index:
            raise ValueError('Reviewed days lie outside the existing scoped history')
        prior = by_key.loc[(sid, anchor)]
        current = by_key.loc[(sid, day)]
        if (pd.isna(prior.stock_ticker) or prior.stock_ticker != symbol
                or pd.isna(prior.identity_span) or current.source_status != 'no_listed_source'):
            raise ValueError('Existing anchor required; no resolved source may be replaced')
        mappings.append(review_mapping(review, records(anchor, symbol), records(day, symbol), scoped_ids=scoped_ids))
    canonical = canonical_candidates(panel, mappings)
    touched = {m['security_id'] for m in mappings}
    selected = canonical[canonical.listed_security_id.isin(touched)]
    raw = []
    for receipt_path, digest in binding['shards'].items():
        path = Path(receipt_path).parent
        if path.parent.name not in set(selected.stock_ticker):
            continue
        if sha(receipt_path) != digest:
            raise ValueError('Selected raw daily shard binding differs')
        bind(path)
        raw.append(pd.read_parquet(path / 'daily.parquet'))
    keys = ['stock_ticker', 'source_date']
    candidates = pd.concat(raw, ignore_index=True).merge(selected.drop(columns='identity_span'),
        on=keys, how='inner', validate='one_to_one')
    if len(candidates) != len(selected):
        raise ValueError('Missing selected raw daily facts')
    clock = before[before.security_id.eq(before.security_id.iloc[0])][
        ['source_date', 'session_open_ns', 'available_ns']].rename(columns={'available_ns': 'stock_available_ns'})
    frames = [before[~before.security_id.isin(touched)]]
    for sid in sorted(touched):
        old = before[before.security_id.eq(sid)]
        overrides = [dict(source_date=r.source_date, stock_ticker=r.stock_ticker, security_id=sid,
            evidence_identity=r.source_selection_evidence) for r in old.itertuples()
            if pd.notna(r.source_selection_evidence)]
        frames.append(security_history(candidates[candidates.listed_security_id.eq(sid)], clock,
                                      security_id=sid, source_overrides=overrides))
    result = pd.concat(frames, ignore_index=True).sort_values(['security_id', 'source_date']).reset_index(drop=True)
    result['provider_composite_figi'] = result.security_id.where(result.stock_ticker.notna()).astype('string')
    result['identity_resolution'] = 'original_selected_identity'
    result.loc[result.stock_ticker.isna(), 'identity_resolution'] = 'unresolved'
    result['identity_resolution_evidence'] = pd.Series(pd.NA, index=result.index, dtype='string')
    result['resolved_share_class_figi'] = pd.Series(pd.NA, index=result.index, dtype='string')
    for mapping in mappings:
        mask = result.security_id.eq(mapping['security_id']) & result.source_date.eq(mapping['source_date'])
        if mask.sum() != 1 or result.loc[mask, 'stock_ticker'].iloc[0] != mapping['stock_ticker']:
            raise ValueError('Reviewed identity was not consumed by the history selector')
        result.loc[mask, 'provider_composite_figi'] = mapping['provider_composite_figi']
        result.loc[mask, 'identity_resolution'] = mapping['identity_resolution']
        result.loc[mask, 'identity_resolution_evidence'] = mapping['identity_resolution_evidence']
        result.loc[mask, 'resolved_share_class_figi'] = mapping['share_class_figi']
    eligible = pd.read_parquet(args.history / 'eligible_sources.parquet')
    comparison = eligible[['security_id', 'source_date', 'stock_ticker_expected']].merge(
        result[['security_id', 'source_date', 'stock_ticker', 'source_status']],
        on=['security_id', 'source_date'], validate='one_to_one', how='left').rename(columns={'stock_ticker': 'stock_ticker_selected'})
    comparison['source_matches'] = comparison.stock_ticker_expected.eq(comparison.stock_ticker_selected).fillna(False)
    if len(result) != len(before) or result.duplicated(['security_id', 'source_date']).any():
        raise ValueError('History grid changed')
    report = dict(security_calendar_rows=len(result), securities=result.security_id.nunique(),
        sessions=result.source_date.nunique(), reviewed_identity_sessions=len(mappings),
        reviewed_symbols=len({m['stock_ticker'] for m in mappings}),
        identity_spans=result.identity_span.nunique(), source_statuses=result.source_status.value_counts().to_dict(),
        eligible_rows=len(comparison), eligible_source_matches=int(comparison.source_matches.sum()),
        eligible_source_unresolved=int((~comparison.source_matches).sum()),
        action_adjustments_applied=False, full_security_admitted=False, research_ready=False)
    if any(sha(p) != h for p, h in inputs.items()):
        raise ValueError('Reviewed history inputs changed')
    with transaction(args.output) as temp:
        result.to_parquet(temp / 'history.parquet', index=False)
        comparison.to_parquet(temp / 'eligible_sources.parquet', index=False)
        for name, value in [('report', report), ('inputs', inputs), ('resolutions', mappings), ('reviews', document)]:
            (temp / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
