"""Extend an immutable action inventory with a named process-date tail capture."""
from pathlib import Path
from collections import Counter
import argparse
import gzip
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.action_inventory import candidate, reconcile
    from nn_meta.v7.cash_actions import record_key
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('inventory', 'supplement', 'request', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / 'nn_meta'):
        raise ValueError('Repository artifact disk required')
    parent, capture = verify(args.inventory), verify(args.supplement)
    declaration = json.loads((args.inventory / 'declaration.json').read_text())
    request = json.loads(args.request.read_text())
    q = capture['query']
    if (request.get('schema') != 'v7-named-missing-action-input-v1'
            or q['endpoint'] != 'https://data.alpaca.markets/v1/corporate-actions'
            or q['params'] != dict(start=request['process_start'], end=request['process_end'],
                symbols=','.join(request['symbols']), limit=1000, sort='asc', region='us', data_quality='all')
            or request['effective_date_end'] != declaration['end']):
        raise ValueError('Capture must match the named missing input request')
    inputs = dict(declaration['inputs'])
    for path, doc in ((args.inventory, parent), (args.supplement, capture)):
        inputs[str(path / 'complete.json')] = sha(path / 'complete.json')
        inputs.update({str(path / n): h for n, h in doc['files'].items()})
    inputs[str(args.request)] = sha(args.request)
    sources = dict(declaration['sources'])
    for path in (Path(__file__), ROOT / 'nn_meta/v7/cash_actions.py'):
        sources[str(path)] = sha(path)
    original = json.loads((args.inventory / 'candidates.json').read_text())
    rows, seen = list(original), {record_key(r): r for r in original}
    counts, ignored, tokens = Counter(), 0, set()
    pages = sorted(n for n in capture['files'] if n.startswith('page-') and n.endswith('.json.gz'))
    if pages != [f'page-{i:04d}.json.gz' for i in range(capture['pages'])]:
        raise ValueError('Contiguous complete page capture required')
    for i, name in enumerate(pages):
        page = json.loads(gzip.decompress((args.supplement / name).read_bytes()))
        token = page.get('next_page_token')
        if bool(token) != (i < len(pages)-1) or (token and token in tokens):
            raise ValueError('Capture pagination did not complete uniquely')
        if token: tokens.add(token)
        for kind, records in page['corporate_actions'].items():
            counts[kind] += len(records)
            for record in records:
                row = candidate('alpaca', kind, record, scoped_symbols=set(declaration['source_symbols']),
                    start=declaration['start'], end=declaration['end'], source=dict(
                        receipt=str(args.supplement / 'complete.json'), payload=str(args.supplement / name),
                        payload_sha256=capture['files'][name]))
                if row is None:
                    ignored += 1
                    continue
                key = record_key(row)
                if key in seen:
                    if row['record_sha256'] != seen[key]['record_sha256']:
                        raise ValueError('Provider revision requires explicit whole-event review')
                    continue
                seen[key] = row; rows.append(row)
    if dict(counts) != capture['counts']:
        raise ValueError('Supplement record counts differ')
    # Preserve original membership identity annotations; do not infer any new ones.
    old_groups = json.loads((args.inventory / 'reconciliation.json').read_text())
    eligible = {(r['symbol'], r['effective_date']): {r['eligible_security_id']}
                for r in old_groups if r['eligible_security_id']}
    groups = reconcile(rows, eligible)
    declaration.update(inputs=inputs, sources=sources,
        supplemental_capture=str(args.supplement), supplemental_request_sha256=sha(args.request))
    report = dict(original_candidate_records=len(original), candidate_records=len(rows),
        added_candidate_records=len(rows)-len(original), ignored_outside_effective_scope=ignored,
        supplement_records=sum(counts.values()), reconciled_groups=len(groups),
        statuses=dict(Counter(r['status'] for r in groups)),
        complex_records=sum(r['category']=='complex' for r in rows), research_ready=False)
    if any(sha(p) != h for p, h in {**inputs, **sources}.items()):
        raise ValueError('Action inventory source changed')
    with transaction(args.output) as temp:
        for name, value in [('declaration', declaration), ('report', report), ('candidates', rows), ('reconciliation', groups)]:
            (temp / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')
        receipt(temp, dict(identity=identity(declaration), research_ready=False))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
