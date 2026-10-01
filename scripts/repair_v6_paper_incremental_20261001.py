"""Reuse verified prior-session histories as the existing producer's repair seed."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vintage_repair', ROOT/'scripts/repair_v6_paper_vintage_20261001.py')
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)
BASE = repair.EVIDENCE
repair.EVIDENCE = BASE/'incremental'
repair.OUTPUT = repair.OUTPUT.with_name(repair.OUTPUT.name+'-r1')
SEED = repair.EVIDENCE/'seed-with-historical-roots'
from nn_meta.live.v6_market import read, save, utcnow
from nn_meta.live.v6_release import sha


def seed():
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    from nn_meta.price_basis import raw_spot_provenance
    before = read(BASE/'before-index.json')
    old = Path(before['path'])
    if sha(old/'manifest.json') != before['sha256']:
        raise ValueError('Parent snapshot changed')
    manifest = read(old/'manifest.json')
    SEED.mkdir(parents=True, exist_ok=True)
    original = ROOT/'nn_meta/data_candidates/audit-repair-20260905-final/cache'
    # Keep original daily history for legacy option roots outside the current
    # universe; the producer merges freshly fetched daily bars into that history.
    replaced = {'underlying_15m.parquet', 'underlying_15m_raw.parquet'}
    for p in original.iterdir():
        target = SEED/p.name
        if p.name not in replaced and not target.exists():
            target.symlink_to(p.resolve(), target_is_directory=p.is_dir())
    counts = {}
    for adjustment, name in [('all','underlying_15m.parquet'),('raw','underlying_15m_raw.parquet')]:
        target = SEED/name
        writer = None
        rows = 0
        try:
            for symbol, record in sorted(manifest['symbols'].items()):
                ref = record['files'][adjustment]
                p = old/ref['path']
                if sha(p) != ref['sha256']:
                    raise ValueError('Parent stock seal changed: '+symbol)
                frame = pd.read_parquet(p).reset_index()
                frame.insert(0, 'symbol', symbol)
                frame.attrs = raw_spot_provenance('15m', provider='alpaca', feed='sip') if adjustment == 'raw' else {}
                table = pa.Table.from_pandas(frame, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(target.with_suffix('.tmp'), table.schema)
                writer.write_table(table)
                rows += len(frame)
        finally:
            if writer is not None:
                writer.close()
        target.with_suffix('.tmp').replace(target)
        counts[adjustment] = rows
    save(repair.EVIDENCE/'seed-provenance.json', dict(parent=before, rows=counts,
        created_at=utcnow().isoformat(), source_files={n:sha(SEED/n) for n in replaced | {'underlying_daily_raw.parquet','underlying_daily.parquet'}},
        scope='Verified prior-session stock histories; unchanged original option observations and metadata'))
    print('Verified September 30 stock seed ready', flush=True)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ['prepare','publish']:
        raise ValueError('Expected prepare or publish')
    if sys.argv[1] == 'publish':
        return repair.main()
    repair.EVIDENCE.mkdir(parents=True, exist_ok=True)
    for name in ['before-index.json','before-paper-manifest.json']:
        source = read(BASE/name)
        target = repair.EVIDENCE/name
        if target.exists() and read(target) != source:
            raise ValueError('Recovery baseline changed')
        save(target, source)
    if not (repair.OUTPUT/'manifest.json').exists():
        seed()
        old = Path(read(BASE/'before-index.json')['path'])
        for ref in read(old/'manifest.json')['new_option_daily']:
            p = old/ref['path']
            if sha(p) != ref['sha256']:
                raise ValueError('Option seal changed')
            target = repair.OUTPUT/ref['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                os.link(p, target)
            if sha(target) != ref['sha256']:
                raise ValueError('Reused option seal changed')
        from scripts.prepare_v6_forward_data import prepare
        prepare(argparse.Namespace(source=SEED, release=repair.RELEASE, anchor=repair.ANCHOR,
                output=repair.OUTPUT, through='2026-09-30', env=ROOT/'.env'))
    result = repair.verify_inputs()
    save(repair.EVIDENCE/'validation.json', result)
    print('Snapshot and fresh raw/adjusted overlap validated', flush=True)


if __name__ == '__main__':
    main()
