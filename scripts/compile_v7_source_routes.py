"""Extend existing aliases with retained publication-backed same-security routes."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pandas as pd
    from nn_meta.v7.source_routes import compile_routes
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify

    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('aliases', 'reviews', 'identities', 'stock-daily', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / 'nn_meta'):
        raise ValueError('Repository artifact disk required')
    sources = {}

    def merge(values):
        for path, digest in values.items():
            if path in sources and sources[path] != digest:
                raise ValueError('Conflicting route source bindings')
            sources[path] = digest

    def bind(path):
        doc = verify(path)
        merge({str(path / 'complete.json'): sha(path / 'complete.json')})
        merge({str(path / name): digest for name, digest in doc['files'].items()})

    bind(args.aliases)
    merge(json.loads((args.aliases / 'report.json').read_text())['sources'])
    bind(args.identities)
    merge(json.loads((args.identities / 'inputs.json').read_text()))
    document = json.loads(args.reviews.read_text())
    if document.get('schema') != 'v7-reviewed-source-routes-v1' or not document.get('routes'):
        raise ValueError('Explicit reviewed source routes required')
    merge({str(args.reviews): sha(args.reviews)})
    stock = []
    for review in document['routes']:
        shard = args.stock_daily / 'shards' / review['stock_ticker'] / review['date'][:4]
        if Path(review['stock_receipt']).resolve() != (shard / 'complete.json').resolve():
            raise ValueError('Route stock receipt differs from selected raw daily shard')
        if Path(review['identity_receipt']).resolve() != (args.identities / 'complete.json').resolve():
            raise ValueError('Route identity receipt differs from captured daily identities')
        bind(shard)
        declaration = json.loads((shard / 'declaration.json').read_text())
        merge(declaration['inputs'])
        merge(declaration['sources'])
        facts = pd.read_parquet(shard / 'daily.parquet')
        stock.append(facts[facts.source_date.eq(review['date'])])
        for evidence in review['evidence']:
            capture = Path(evidence['capture'])
            if sha(capture / 'complete.json') != evidence['receipt_sha256']:
                raise ValueError('Reviewed publication receipt changed')
            bind(capture)
            if sha(capture / 'response.bin') != evidence['payload_sha256']:
                raise ValueError('Reviewed publication content changed')
    for path in (Path(__file__), ROOT / 'nn_meta/v7/source_routes.py',
                 ROOT / 'nn_meta/v7/action_inventory.py', ROOT / 'nn_meta/v7/storage.py',
                 ROOT / 'nn_meta/v7/runtime.py'):
        merge({str(path): sha(path)})
    if any(sha(path) != digest for path, digest in sources.items()):
        raise ValueError('Route source bindings changed')
    aliases = pd.read_parquet(args.aliases / 'session_aliases.parquet')
    result = compile_routes(aliases, document['routes'],
        pd.read_parquet(args.identities / 'identities.parquet'), pd.concat(stock, ignore_index=True))
    report = dict(resolved_sessions=len(result), added_sessions=len(result) - len(aliases),
        scope='exact-session same-security source routing; no membership or action adjustment',
        research_ready=False, sources=sources)
    with transaction(args.output) as temp:
        result.to_parquet(temp / 'session_aliases.parquet', index=False)
        (temp / 'reviews.json').write_text(json.dumps(document, indent=2) + '\n')
        (temp / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        if any(sha(path) != digest for path, digest in sources.items()):
            raise ValueError('Route sources changed during compilation')
        receipt(temp, dict(identity=identity(sources), research_ready=False))
    print(json.dumps({k: v for k, v in report.items() if k != 'sources'}, indent=2))


if __name__ == '__main__':
    main()
