"""Exact bounded-memory comparison of catalog keys, first observations and derived fields."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sorted_keys(source, target, scratch):
    import polars as pl
    import pyarrow.parquet as pq
    count = 0
    with target.open('wb') as output:
        sorter = subprocess.Popen(['sort', '--parallel=1', '--buffer-size=256M',
                                   '--temporary-directory=' + str(scratch)], stdin=subprocess.PIPE,
                                  stdout=output, env={**os.environ, 'LC_ALL': 'C'})
        try:
            for batch in pq.ParquetFile(source).iter_batches(batch_size=65536):
                frame = pl.from_arrow(batch)
                valid = frame.select(
                    (pl.col('root') == pl.col('ticker').str.extract(r'^O:([A-Z]+)', 1)) &
                    (pl.col('expiry') == pl.col('ticker').str.slice(-15, 6).str.strptime(pl.Date, format='%y%m%d')) &
                    (pl.col('right') == pl.col('ticker').str.slice(-9, 1)) &
                    (pl.col('strike') == pl.col('ticker').str.slice(-8).cast(pl.Float64) / 1000) &
                    (pl.col('first_seen') == pl.from_epoch('first_seen_ns', time_unit='ns').dt.replace_time_zone('UTC')
                     .dt.convert_time_zone('America/New_York').dt.date())).to_series()
                if valid.null_count() or not valid.all():
                    raise ValueError('Catalog derived fields disagree with contract/observation identity')
                lines = frame.select(pl.concat_str('ticker', pl.col('first_seen_ns').cast(pl.String), separator='\t')).to_series()
                sorter.stdin.write(('\n'.join(lines) + '\n').encode())
                count += frame.height
        finally:
            sorter.stdin.close()
            code = sorter.wait()
        if code:
            raise RuntimeError('External bounded sort failed')
    return count


def main():
    from nn_meta.v7.runtime import configure_threads
    configure_threads(1)
    from nn_meta.v7.storage import transaction, receipt, verify, sha, identity
    ap = argparse.ArgumentParser(description=__doc__)
    for key in ('left', 'right', 'output'):
        ap.add_argument('--' + key, type=Path, required=True)
    args = ap.parse_args()
    if shutil.which('sort') is None:
        raise RuntimeError('Coreutils sort is required for the bounded exact comparison')
    verify(args.left.parent)
    verify(args.right.parent)
    inputs = {str(p): sha(p) for p in (args.left, args.right)}
    began = time.perf_counter()
    with transaction(args.output) as temp:
        counts = [sorted_keys(p, temp / name, temp) for p, name in ((args.left, 'left.tsv'), (args.right, 'right.tsv'))]
        same = counts[0] == counts[1]
        with (temp / 'left.tsv').open('rb') as left, (temp / 'right.tsv').open('rb') as right:
            while True:
                a, b = left.read(4 * 1024**2), right.read(4 * 1024**2)
                if a != b:
                    same = False
                    break
                if not a:
                    break
        report = {'records': counts, 'exact_equal': same, 'seconds': time.perf_counter() - began,
                  'canonical_sha256': {name: sha(temp / name) for name in ('left.tsv', 'right.tsv')}}
        (temp / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        # Retain the exact comparison and hashes, not disposable duplicate sort files.
        (temp / 'left.tsv').unlink()
        (temp / 'right.tsv').unlink()
        receipt(temp, {'identity': identity({'inputs': inputs, 'code': sha(__file__)}), 'exact_equal': same})
    print(json.dumps(report, indent=2))
    if not same:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
