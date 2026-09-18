"""Seal finite exact-date reviews of cash records for unrelated ticker reuses."""
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
    from nn_meta.v7.action_scope import other_instrument_treatments
    from nn_meta.v7.listed_evidence import ListedEvidence
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('history', 'actions', 'listed-captures', 'reviews', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if (not args.output.resolve().is_relative_to(ROOT / 'nn_meta')
            or shutil.disk_usage(ROOT).free < 100 * 1024**3):
        raise ValueError('Repository artifact disk and 100 GiB reserve required')
    inputs = {}

    def merge(values):
        for path, digest in values.items():
            if path in inputs and inputs[path] != digest:
                raise ValueError('Conflicting original source bindings')
            inputs[path] = digest

    for path in (args.history, args.actions):
        doc = verify(path)
        merge({str(path / 'complete.json'): sha(path / 'complete.json')})
        merge({str(path / n): h for n, h in doc['files'].items()})
        merge(json.loads((path / 'inputs.json').read_text()))
    for path in [Path(__file__), args.reviews, *[ROOT / 'nn_meta/v7' / (n + '.py') for n in
            ('action_scope', 'listed_evidence', 'daily_identities', 'action_inventory', 'cash_actions', 'storage', 'runtime')]]:
        merge({str(path): sha(path)})
    doc = json.loads(args.reviews.read_text())
    if doc.get('schema') != 'v7-unrelated-ticker-reuse-reviews-v1':
        raise ValueError('Finite unrelated-instrument reviews required')
    history = pd.read_parquet(args.history / 'history.parquet')
    scoped = set(history.security_id)
    reader = ListedEvidence(args.listed_captures)
    witnesses = {}
    for symbol, witness in doc['scoped_witnesses'].items():
        row = reader.record(witness['symbol'], witness['date'])
        selected = history[history.source_date.eq(witness['date']) & history.security_id.eq(witness['security_id'])]
        if (not row or row.get('composite_figi') != witness['security_id']
                or witness['security_id'] not in scoped or identity(row) != witness['record_sha256']
                or row.get('share_class_figi') != witness['share_class_figi']
                or not witness['share_class_figi'] or len(selected) != 1
                or selected.stock_ticker.iloc[0] != witness['symbol']):
            raise ValueError('Captured scoped instrument witness differs')
        witnesses[symbol] = row
    listings = {}
    for review in doc['reviews']:
        symbol, day = review['symbol'], review['effective_date']
        row = reader.record(symbol, day)
        if symbol not in witnesses or not row or row.get('share_class_figi') == witnesses[symbol]['share_class_figi']:
            raise ValueError('Unrelated instruments must have distinct captured share classes')
        listings[symbol, day] = row
    merge(reader.inputs)
    treatments, pending = other_instrument_treatments(
        json.loads((args.actions / 'unresolved.json').read_text()), doc['reviews'], listings,
        scoped_ids=scoped, selected_keys=set(zip(history.stock_ticker.dropna(), history.loc[history.stock_ticker.notna(), 'source_date'])))
    report = dict(reviewed_groups=len(treatments), reviewed_original_records=sum(len(t['replaces']) for t in treatments),
        symbols=sorted({t['symbol'] for t in treatments}), unresolved_original_records=len(pending),
        new_study_exclusions=0, chart_actions_added=0, held_entitlements_inferred=False, research_ready=False)
    if any(sha(p) != h for p, h in inputs.items()):
        raise ValueError('Review source changed')
    with transaction(args.output) as temp:
        for name, value in [('report', report), ('inputs', inputs), ('reviews', doc),
                            ('treatments', treatments), ('unresolved', pending)]:
            (temp / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
        receipt(temp, dict(identity=identity(inputs), research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
