"""One-shot: rewrite an existing universe.parquet / contracts.parquet sorted by
underlying (stable) in small row groups, so `HybridCachedProvider._get_slice`
predicate reads skip row groups. Rows and per-underlying order are unchanged;
only the file layout is. derive_contracts.py writes new caches this way already.

    NN_META_POOL=v5 ./venv/bin/python scripts/sort_universe.py [--cache nn_meta/data_cache_v5]
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import pyarrow.parquet as pq
from nn_meta import config
from v3.derive_contracts import UNIVERSE_ROW_GROUP


def resort(path: Path) -> None:
    df = pd.read_parquet(path)
    before = pq.read_metadata(path).num_row_groups
    out = df.sort_values("underlying", kind="stable").reset_index(drop=True)
    assert len(out) == len(df)
    tmp = path.with_suffix(".sorted.tmp")
    out.to_parquet(tmp, index=False, row_group_size=UNIVERSE_ROW_GROUP)
    bak = path.with_suffix(".parquet.unsorted.bak")
    if not bak.exists():
        path.replace(bak)
    tmp.replace(path)
    after = pq.read_metadata(path).num_row_groups
    print(f"{path.name}: {len(out):,} rows, {df['underlying'].nunique()} underlyings, "
          f"row groups {before} → {after}; original kept as {bak.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=config.DATA_CACHE)
    args = ap.parse_args()
    for name in ("universe.parquet", "contracts.parquet"):
        p = args.cache / name
        if p.exists():
            resort(p)


if __name__ == "__main__":
    main()
