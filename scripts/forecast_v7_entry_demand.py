#!/usr/bin/env python3
"""Count exact saved proposal decisions for V7 demand storage planning only."""
from __future__ import annotations
import argparse
from collections import defaultdict
import concurrent.futures
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def count_decisions(paths, expected_rows):
    """Bounded column reads, with symbol/right identity retained across timeframes."""
    import numpy as np
    import pyarrow.parquet as pq
    from nn_meta.v7.compact_proposals import SCHEMA
    values = defaultdict(list)
    rows = 0
    for path in paths:
        source = pq.ParquetFile(path)
        if not source.schema_arrow.equals(SCHEMA):
            raise ValueError('Foreign compact proposal schema')
        for batch in source.iter_batches(batch_size=65536, columns=['decision_ns', 'is_put', 'symbol']):
            if any(c.null_count for c in batch.columns):
                raise ValueError('Missing decision identity')
            clocks = batch.column(0).to_numpy()
            if len(clocks) and ((clocks <= 0).any() or (clocks > np.iinfo(np.int64).max // 2).any()):
                raise ValueError('Decision clock outside exact encoding range')
            keys = clocks * 2 + batch.column(1).to_numpy(zero_copy_only=False)
            symbols = batch.column(2)
            codes = symbols.indices.to_numpy()
            for index, name in enumerate(symbols.dictionary.to_pylist()):
                if not isinstance(name, str) or not name:
                    raise ValueError('Missing dated symbol')
                selected = keys[codes == index]
                if len(selected):
                    values[name].append(np.unique(selected))
            rows += batch.num_rows
    if rows != expected_rows:
        raise ValueError('Proposal census changed')
    return {name: np.unique(np.concatenate(parts)) for name, parts in values.items()}, rows


def census_security(payload):
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import numpy as np
    from nn_meta.v7.storage import verify, sha, identity, receipt, transaction
    from scripts.run_v7_entry_demand import read
    sid, root, output, expected, proof_hash = payload
    root, output = Path(root), Path(output)
    binding = dict(security_id=sid, audited_receipts=expected, proof_sha256=proof_hash,
                   script_sha256=sha(__file__))
    destination = output / 'securities' / sid
    if destination.exists():
        verify(destination, expected_identity=identity(binding))
        return read(destination / 'report.json')
    combined = defaultdict(list)
    feature_count = total_rows = 0
    sources = {}
    per_timeframe = {}
    for minutes in (5, 15, 30):
        base = root / sid / str(minutes) / 'proposals'
        summary = base / 'summary'
        if sha(summary / 'complete.json') != expected[str(minutes)]['proposal_receipt_sha256']:
            raise ValueError('Census parent differs from deep audit')
        verify(summary)
        header = verify(base / 'declaration')
        declaration = read(base / 'declaration/declaration.json')
        report = read(summary / 'report.json')
        if (header['identity'] != identity(declaration) or declaration['security_id'] != sid or
                any(v['signal_minutes'] != minutes for v in declaration['variants']) or
                report['proposals'] != expected[str(minutes)]['proposals']):
            raise ValueError('Foreign proposal scope')
        paths = []
        for part in report['batches']:
            directory = base / 'batches' / str(part['batch'])
            if sha(directory / 'complete.json') != part['receipt_sha256']:
                raise ValueError('Census batch receipt changed')
            doc = verify(directory)
            sources[str(directory / 'proposals.parquet')] = doc['files']['proposals.parquet']
            paths.append(directory / 'proposals.parquet')
        groups, count = count_decisions(paths, report['proposals'])
        distinct = sum(map(len, groups.values()))
        per_timeframe[str(minutes)] = dict(proposals=count, feature_decisions=distinct)
        feature_count += distinct
        total_rows += count
        for name, clocks in groups.items():
            combined[name].append(clocks)
        sources[str(summary / 'complete.json')] = expected[str(minutes)]['proposal_receipt_sha256']
    selections = sum(len(np.unique(np.concatenate(parts))) for parts in combined.values())
    if any(sha(p) != h for p, h in sources.items()):
        raise ValueError('Census source changed while reading')
    result = dict(security_id=sid, proposals=total_rows, feature_decisions=feature_count,
                  selection_decisions=selections, targets=5 * selections,
                  maximum_requests=10 * feature_count, maximum_links=10 * feature_count,
                  timeframes=per_timeframe, research_ready=False)
    with transaction(destination) as temp:
        (temp / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
        (temp / 'binding.json').write_text(json.dumps(binding, indent=2) + '\n')
        receipt(temp, dict(identity=identity(binding)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--completion', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / 'nn_meta/validation'):
        parser.error('Use a separate validation directory')
    from nn_meta.v7.runtime import worker_pool
    from nn_meta.v7.storage import sha, receipt, transaction, identity, verify
    from scripts.run_v7_entry_demand import CatalogProof, write
    proof = CatalogProof(args.completion)
    args.output.mkdir(parents=True, exist_ok=True)
    payloads = [(sid, str(proof.root), str(args.output.resolve()),
                 {str(m): proof.receipts[sid, m] for m in (5, 15, 30)},
                 sha(args.completion / 'complete.json')) for sid in proof.security_ids]
    results = []
    started = last = time.monotonic()
    with worker_pool(args.workers, threads=1) as pool:
        futures = [pool.submit(census_security, p) for p in payloads]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
            progress = dict(stage='entry-demand-census', completed=len(results), total=len(payloads),
                            elapsed_seconds=time.monotonic() - started)
            write(args.output / 'progress.json', progress)
            if time.monotonic() - last >= 30:
                print(json.dumps(progress), flush=True)
                last = time.monotonic()
    proof.check_evidence()
    totals = {key: sum(row[key] for row in results) for key in
              ('proposals', 'feature_decisions', 'selection_decisions', 'targets', 'maximum_requests', 'maximum_links')}
    report = dict(schema='v7-entry-demand-census-v1', securities=len(results), **totals,
                  method='exact unique symbol/decision_ns/right per timeframe and across timeframes',
                  assumption='Request/link ceilings assume all five targets select distinct contracts; actual union may be smaller.',
                  elapsed_seconds=time.monotonic()-started, research_ready=False,
                  inputs={str(args.completion.resolve() / 'complete.json'): sha(args.completion / 'complete.json'),
                          str(Path(__file__).resolve()): sha(__file__)},
                  security_receipts={r['security_id']: sha(args.output / 'securities' / r['security_id'] / 'complete.json') for r in results})
    summary = args.output / 'summary'
    if summary.exists():
        verify(summary)
    else:
        with transaction(summary) as temp:
            (temp / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
            receipt(temp, dict(identity=identity(report)))
    print(json.dumps(totals, indent=2), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
