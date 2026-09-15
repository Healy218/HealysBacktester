"""Bounded numerical shards: shared chart, parameter and tick vectors plus row fields."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

from nn_meta.v7.rows import schema, TRADE
from nn_meta.option_tick_dataset import NUMERIC_FEATURES
from nn_meta.v7.storage import transaction, receipt, verify, identity

MAX_ROWS = 65536


def partitions():
    names = schema()
    params = [n for n in names if n.startswith(('strat_', 'param_'))]
    ticks = list(NUMERIC_FEATURES)
    per_row = [*TRADE, 'ma_gap', 'px_vs_fast']
    chart = [n for n in names if n not in params + ticks + per_row]
    return {'chart': chart, 'parameters': params, 'ticks': ticks, 'row': per_row}


def write_shard(path, rows, metadata, *, input_identity):
    if (tuple(rows.columns) != schema() or not 0 < len(rows) <= MAX_ROWS
            or rows.index.has_duplicates or len(metadata) != len(rows)
            or 'row_id' not in metadata or metadata.row_id.astype(str).tolist() != rows.index.astype(str).tolist()):
        raise ValueError('Bounded aligned full-schema rows and distinct row IDs required')
    values = rows.to_numpy(dtype=np.float32)
    if np.isinf(values).any():
        raise ValueError('Infinite or float32-overflowing model features')
    frame = pd.DataFrame(values, columns=rows.columns)
    groups, codes, shapes, payload_bytes = partitions(), [], {}, 0
    declaration = {'schema': 'v7-factorized-float32-v1', 'input_identity': input_identity,
                   'columns': list(schema()), 'groups': groups, 'rows': len(rows)}
    with transaction(path) as temp:
        for name, columns in groups.items():
            block = frame[columns]
            if name == 'row':
                unique = block.to_numpy(dtype=np.float32)
            else:
                code, unique_index = pd.factorize(pd.MultiIndex.from_frame(block), sort=False)
                if (code < 0).any():
                    raise ValueError('Missing vector identity')
                unique = unique_index.to_frame(index=False).to_numpy(dtype=np.float32)
                codes.append(code.astype(np.int32))
            np.save(temp / (name + '.npy'), unique, allow_pickle=False)
            shapes[name] = list(unique.shape)
            payload_bytes += unique.nbytes
        references = np.column_stack(codes)
        np.save(temp / 'references.npy', references, allow_pickle=False)
        payload_bytes += references.nbytes
        metadata.to_parquet(temp / 'metadata.parquet', index=False)
        (temp / 'declaration.json').write_text(json.dumps(declaration, indent=2) + '\n')
        receipt(temp, {'identity': identity(declaration), 'rows': len(rows), 'shapes': shapes,
                       'float32_dense_payload_bytes': values.nbytes,
                       'factorized_payload_bytes': payload_bytes, 'research_ready': False})


class FactorizedRows:
    def __init__(self, path):
        self.path = Path(path)
        self.receipt = verify(self.path)
        declaration = json.loads((self.path / 'declaration.json').read_text())
        if (declaration['schema'] != 'v7-factorized-float32-v1' or declaration['columns'] != list(schema())
                or declaration['groups'] != partitions() or identity(declaration) != self.receipt['identity']):
            raise ValueError('Factorized schema or lineage changed')
        self.groups = partitions()
        self.count = declaration['rows']
        if not 0 < self.count <= MAX_ROWS:
            raise ValueError('Unbounded shard')
        self.references = np.load(self.path / 'references.npy', mmap_mode='r', allow_pickle=False)
        self.arrays = {k: np.load(self.path / (k + '.npy'), mmap_mode='r', allow_pickle=False) for k in self.groups}
        if self.references.shape != (self.count, 3) or self.references.dtype != np.dtype('int32'):
            raise ValueError('Invalid factor references')
        for i, (key, names) in enumerate(self.groups.items()):
            array = self.arrays[key]
            if array.ndim != 2 or array.shape[1] != len(names) or array.dtype != np.dtype('float32'):
                raise ValueError('Invalid factor shape or dtype')
            if key == 'row':
                if len(array) != self.count:
                    raise ValueError('Incomplete per-row features')
            elif (self.references[:, i] < 0).any() or (self.references[:, i] >= len(array)).any():
                raise ValueError('Out-of-range factor reference')
        self.positions = {k: [schema().index(n) for n in names] for k, names in self.groups.items()}

    def __len__(self):
        return self.count

    def take(self, indices):
        indices = np.asarray(indices)
        if (indices.ndim != 1 or indices.dtype.kind not in 'iu' or len(indices) > MAX_ROWS
                or (indices < 0).any() or (indices >= self.count).any()):
            raise ValueError('Bounded valid row indices required')
        result = np.empty((len(indices), len(schema())), dtype=np.float32)
        for i, (key, array) in enumerate(self.arrays.items()):
            positions = indices if key == 'row' else self.references[indices, i]
            result[:, self.positions[key]] = array[positions]
        return result


def training_sequence(path, *, indices):
    """An explicit fold selection; LightGBM samples and reads bounded batches."""
    import lightgbm as lgb
    store = FactorizedRows(path)
    selected = np.asarray(indices)
    if (selected.ndim != 1 or selected.dtype.kind not in 'iu' or not len(selected)
            or len(set(selected.tolist())) != len(selected)
            or (selected < 0).any() or (selected >= len(store)).any()):
        raise ValueError('Explicit distinct training row selection required')

    class ShardSequence(lgb.Sequence):
        batch_size = 4096

        def __len__(self):
            return len(selected)

        def __getitem__(self, item):
            chosen = selected[item]
            if np.isscalar(chosen):
                # LightGBM's initial bin sampling requires float64 row views.
                return store.take(np.array([chosen], dtype=np.int64))[0].astype(np.float64)
            return store.take(np.asarray(chosen, dtype=np.int64))

    return ShardSequence()
