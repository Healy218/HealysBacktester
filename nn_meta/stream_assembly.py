"""Bounded-memory assembly of already-built, provenance-checked symbol shards."""
from __future__ import annotations
import gc
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def assemble_streaming(rows_dir=None, marks_dir=None, *, membership=False):
    from nn_meta import build_meta_dataset as b, config, mark_stream
    from nn_meta.feature_contract import CONTRACT_VERSION, baseline_spec_fingerprint
    from nn_meta.weekly_expiry import dte_grid_for
    from nn_meta.universe_pit import membership_mask
    rows_dir, marks_dir = Path(rows_dir or b.ROWS_DIR), Path(marks_dir or b.MARKS_DIR)
    parts = sorted(rows_dir.glob('*.parquet'))
    if not parts:
        raise ValueError('No row shards to assemble')
    spec = b.load_spec()
    expected_symbols = set(spec['symbols'])
    if {p.stem for p in parts} != expected_symbols:
        raise ValueError('Row shards do not exactly cover the frozen eligible symbols')
    for p in parts:
        if b._read_provenance(p) != b._provenance(spec['symbols'][p.stem], dte_grid_for(p.stem, spec)):
            raise ValueError(f'Row provenance mismatch: {p.name}')
    input_schema = pa.unify_schemas([pq.read_schema(p).remove_metadata() for p in parts],
                                   promote_options='permissive')
    surface = b.load_surface_features()
    beta = b.rolling_beta_60d().sort_values('date')
    destination = config.META_DATASET_PARQUET
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix('.stream.tmp')
    marks_destination = mark_stream.mark_stream_path(destination)
    marks_tmp = marks_destination.with_suffix('.stream.tmp')
    writer = mark_writer = None
    totals = dict(input_rows=0, membership_rows=0, dataset_rows=0, mark_rows=0, symbols=0)
    schema = None
    try:
        for p in parts:
            rows = pd.read_parquet(p)
            mp = marks_dir / p.name
            marks = pd.read_parquet(mp) if mp.exists() else None
            if not b._marks_cover(rows, marks):
                raise ValueError(f'Incomplete marks for {p.name}')
            totals['input_rows'] += len(rows)
            if membership and not rows.empty:
                rows = rows.loc[membership_mask(rows['symbol'], rows['entry_date'])].reset_index(drop=True)
            totals['membership_rows'] += len(rows)
            if rows.empty:
                continue
            ds = b.join_surface_asof(rows, surface)
            ds = b.add_context_features(ds, surface, beta=beta)
            labeled = ds['net_return'].notna()
            ds['label'] = np.where(labeled, (ds['net_return'].fillna(0) > 0).astype(float), np.nan)
            ds['label_excess'] = np.where(labeled & ds['und_period_return'].notna(),
                                          (ds['net_return'].fillna(0) > ds['und_period_return'].fillna(0)).astype(float), np.nan)
            ds['split'] = b.assign_split(ds['entry_date'])
            ds = ds.loc[ds['split'] != 'purged'].reset_index(drop=True)
            if ds.empty:
                continue
            # Drop unused categorical levels, not numeric precision. The resulting
            # rows retain the same feature/label values as the reference assembler.
            for col in ds.select_dtypes('category'):
                ds[col] = ds[col].astype(str)
            ds.attrs = {'feature_contract_version': CONTRACT_VERSION,
                        'baseline_spec_sha256': baseline_spec_fingerprint(spec)}
            filled = ds.loc[ds['executed'] & ds['fill_lag_s'].notna(), 'fill_lag_s']
            if (filled < 0).any():
                raise ValueError('Option fill precedes decision')
            table = pa.Table.from_pandas(ds, preserve_index=False)
            if writer is None:
                # An unfilled first symbol must not lock optional fields to null.
                fields = []
                for f in table.schema:
                    dtype = input_schema.field(f.name).type if f.name in input_schema.names else f.type
                    if pa.types.is_dictionary(dtype):
                        dtype = dtype.value_type
                    if pa.types.is_null(dtype):
                        raise ValueError(f'Cannot infer type for entirely null column {f.name}')
                    fields.append(pa.field(f.name, dtype))
                schema = pa.schema(fields, metadata=table.schema.metadata)
                writer = pq.ParquetWriter(tmp, schema)
            writer.write_table(table.cast(schema))
            if marks is not None and not marks.empty:
                keep = mark_stream.stable_trade_id(ds)
                mk = mark_stream.validate_mark_stream(marks)
                mk = mk.loc[mk['trade_id'].isin(keep)]
                if not mk.empty:
                    if mark_writer is None:
                        mark_writer = pq.ParquetWriter(marks_tmp, mark_stream._ARROW_SCHEMA)
                    mark_writer.write_table(pa.Table.from_pandas(mk, preserve_index=False).cast(mark_stream._ARROW_SCHEMA))
                    totals['mark_rows'] += len(mk)
            totals['dataset_rows'] += len(ds)
            totals['symbols'] += 1
            print(json.dumps({'assembly': p.stem, **totals}), flush=True)
            del ds, table, rows, marks
            gc.collect()
    finally:
        if writer is not None:
            writer.close()
        if mark_writer is not None:
            mark_writer.close()
    if not totals['dataset_rows'] or not totals['mark_rows']:
        raise ValueError('Assembly requires nonempty rows and complete option marks')
    # Completion receipt is the pair's admission gate; each artifact is atomic.
    marks_tmp.replace(marks_destination)
    tmp.replace(destination)
    receipt = destination.with_suffix('.assembly.json')
    receipt.write_text(json.dumps({'version': 1, 'complete': True, **totals}, indent=2)+'\n')
    return totals
