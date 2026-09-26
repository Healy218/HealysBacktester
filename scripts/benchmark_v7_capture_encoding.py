#!/usr/bin/env python3
"""Measure a reversible column encoding on captured samples, without migration.

The candidate is an experiment, not an implemented archive/consumer format.
Every decoded record and both original metadata files must round-trip exactly.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def columns(records):
    keys = sorted({key for row in records for key in row})
    return dict(count=len(records), keys=keys,
                values=[[row.get(key) for row in records] for key in keys],
                absent=[[i for i, row in enumerate(records) if key not in row] for key in keys])


def records(encoded):
    result = [{} for _ in range(encoded['count'])]
    for key, values, absent in zip(encoded['keys'], encoded['values'], encoded['absent'], strict=True):
        if len(values) != len(result):
            raise ValueError('Column count drift')
        missing = set(absent)
        for i, value in enumerate(values):
            if i not in missing:
                result[i][key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forecast', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--captures', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    import pyarrow as pa
    from options.data.massive_ticks import canonical_bytes
    from nn_meta.v7.storage import verify, sha, identity, transaction, receipt
    from scripts.capture_v7_volume_sample import forecast, measure
    from scripts.download_v7_data import save
    for name in ('forecast', 'plan', 'captures', 'output'):
        setattr(args, name, getattr(args, name).resolve())
    if not args.output.is_relative_to(ROOT / 'nn_meta/validation'):
        parser.error('Use a separate validation output')
    verify(args.forecast); verify(args.plan)
    source = json.loads((args.forecast / 'report.json').read_text())
    plan = json.loads((args.plan / 'report.json').read_text())
    binding = dict(forecast_sha256=sha(args.forecast / 'complete.json'),
                   plan_sha256=sha(args.plan / 'complete.json'), source_sha256=sha(__file__))
    if args.output.exists():
        verify(args.output, expected_identity=identity(binding))
        return
    codec = pa.Codec('zstd', compression_level=9)
    measurements, sizes = {}, {}
    for sample in plan['samples']:
        for item in sample['captures'].values():
            cid = item['capture_id']
            checked = measure(item, args.captures)
            if checked['receipt_sha256'] != source['measurements'][cid]['receipt_sha256']:
                raise ValueError('Sample receipt drift')
            folder = args.captures / cid
            original = gzip.decompress((folder / 'records.json.gz').read_bytes())
            data = json.loads(original)
            encoded = canonical_bytes(columns(data))
            compressed = bytes(codec.compress(encoded))
            decoded = json.loads(bytes(codec.decompress(compressed, len(encoded))))
            if canonical_bytes(records(decoded)) != original:
                raise ValueError('Candidate encoding changes original record bytes')
            # Preserve exact original receipt/manifest bytes in each indexed blob.
            metadata = canonical_bytes({name: (folder / name).read_text()
                                        for name in ('capture.json', 'complete.json')})
            packed_metadata = bytes(codec.compress(metadata))
            if bytes(codec.decompress(packed_metadata, len(metadata))) != metadata:
                raise ValueError('Candidate metadata roundtrip failed')
            # A declared 128-byte index allowance is modeled, not measured
            # filesystem/container overhead. Keep that limitation explicit.
            size = len(compressed)+len(packed_metadata)+128
            sizes[cid] = dict(column_zstd_bytes=len(compressed), metadata_zstd_bytes=len(packed_metadata),
                              modeled_index_bytes=128, original_bytes=checked['logical_bytes'])
            measurements[cid] = dict(ok=True, logical_bytes=size)
    result = forecast(plan, measurements)
    result.update(schema='v7-capture-encoding-benchmark-v1', roundtrip_verified=len(measurements),
                  candidate='JSON columns plus zstd level 9; exact metadata text separately compressed',
                  modeled_index_bytes_per_capture=128, production_archive_implemented=False,
                  original_estimated_bytes=source['estimated_capture_bytes'], sizes=sizes,
                  excludes='Container/filesystem overhead beyond modeled index, request mappings, references and execution paths')
    with transaction(args.output) as temporary:
        save(temporary / 'binding.json', binding)
        save(temporary / 'report.json', result)
        receipt(temporary, dict(identity=identity(binding), research_ready=False))
    print(json.dumps({k: v for k, v in result.items() if k not in ('strata', 'sizes')}), flush=True)


if __name__ == '__main__':
    main()
