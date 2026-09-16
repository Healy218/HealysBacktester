"""Disk-backed fold selections over immutable, bounded factorized shards.

Bounded feature reads do not imply a bounded LightGBM binned dataset. The
integrated resource gate must measure that separate allocation before launch.
"""
from functools import lru_cache
import json
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from nn_meta.v7.evaluation import fold_masks
from nn_meta.v7.factorized import FactorizedRows, MAX_ROWS
from nn_meta.v7.rows import schema
from nn_meta.v7.storage import identity, receipt, sha, transaction, verify


def prepare_fold(paths, fold, calendar, output, *, embargo_sessions=10):
    paths = [Path(p).resolve() for p in paths]
    if not paths or len(set(paths)) != len(paths):
        raise ValueError('Distinct nonempty source shards required')
    inputs = {str(p/'complete.json'): sha(p/'complete.json') for p in paths}
    declaration = dict(schema='v7-factorized-fold-v1', fold=fold, embargo_sessions=embargo_sessions,
                       ordered_shards=[str(p) for p in paths],
                       source_hashes={name: sha(Path(__file__).with_name(name)) for name in
                                      ('training_data.py', 'factorized.py', 'rows.py', 'evaluation.py')},
                       calendar=dict(coverage_start=calendar.start, coverage_end=calendar.end,
                           bounds_utc={d: [str(x) for x in calendar.bounds(d)] for d in sorted(calendar.sessions)}),
                       inputs=inputs, feature_columns=list(schema()))
    if Path(output).exists():
        verify(output, expected_identity=identity(declaration))
        # Reuse only the exact source order, fold, calendar and runtime code.
        # Each source payload is reverified without assembling the full matrix.
        for path in paths:
            FactorizedRows(path)
        FoldRows(output, 'train')
        FoldRows(output, 'validation')
        return json.loads((Path(output)/'report.json').read_text())
    totals = dict(source=0, train=0, validation=0, incomplete=0, outside_or_purged=0)
    parts = []
    with transaction(output) as temp:
        # A disk index catches cross-shard duplicates without keeping all IDs in RAM.
        with sqlite3.connect(temp/'row_ids.sqlite') as seen:
            seen.execute('CREATE TABLE row_ids (row_id TEXT PRIMARY KEY) WITHOUT ROWID')
            for ordinal, path in enumerate(paths):
                store = FactorizedRows(path)
                meta = pd.read_parquet(path/'metadata.parquet')
                required = {'row_id', 'decision_ns', 'label_end_ns', 'label_complete', 'net_return'}
                if not required.issubset(meta) or len(meta) != len(store) or meta.row_id.isna().any():
                    raise ValueError('Complete aligned label metadata required')
                if (not pd.api.types.is_integer_dtype(meta.decision_ns)
                        or meta.decision_ns.isna().any() or (meta.decision_ns <= 0).any()):
                    raise ValueError('Exact integer decision clocks required')
                ends = meta.label_end_ns.dropna()
                if len(ends) and (not pd.api.types.is_integer_dtype(ends) or (ends <= 0).any()):
                    raise ValueError('Exact nullable integer label clocks required')
                try:
                    seen.executemany('INSERT INTO row_ids VALUES (?)',
                                     [(str(v),) for v in meta.row_id])
                except sqlite3.IntegrityError:
                    raise ValueError('Duplicate row identity across source shards') from None
                clocks = pd.DataFrame(dict(decision_at=pd.to_datetime(meta.decision_ns, unit='ns', utc=True),
                     label_end=pd.to_datetime(meta.label_end_ns, unit='ns', utc=True),
                     label_complete=meta.label_complete))
                train, validation = fold_masks(clocks, fold, calendar, embargo_sessions=embargo_sessions)
                complete = meta.label_complete
                if (meta.loc[complete, 'label_end_ns'].isna().any()
                        or not np.isfinite(meta.loc[complete, 'net_return'].to_numpy(float)).all()):
                    raise ValueError('Completed labels require finite returns and full settlement clocks')
                part = dict(source=str(path), ordinal=ordinal, source_rows=len(meta))
                for name, mask in (('train', train), ('validation', validation)):
                    indices = np.flatnonzero(mask.to_numpy()).astype(np.int32)
                    target = meta.loc[mask, 'net_return'].to_numpy(dtype=np.float64)
                    np.save(temp/f'{ordinal}-{name}-indices.npy', indices, allow_pickle=False)
                    np.save(temp/f'{ordinal}-{name}-returns.npy', target, allow_pickle=False)
                    part[name] = len(indices)
                    totals[name] += len(indices)
                totals['source'] += len(meta)
                totals['incomplete'] += int((~complete).sum())
                totals['outside_or_purged'] += int((complete & ~train & ~validation).sum())
                excluded = meta.loc[~train & ~validation].copy()
                excluded['exclusion_reason'] = np.where(excluded.label_complete,
                    'outside_fold_or_purged_horizon', 'incomplete_label')
                excluded.to_parquet(temp/f'{ordinal}-excluded.parquet', index=False)
                parts.append(part)
            seen.commit()
        if not totals['train'] or not totals['validation']:
            raise ValueError('Fold must retain both training and validation observations')
        if totals['source'] != sum(totals[k] for k in ('train', 'validation', 'incomplete', 'outside_or_purged')):
            raise ValueError('Fold rows do not reconcile')
        if any(sha(p) != digest for p, digest in inputs.items()):
            raise ValueError('Source shard receipt changed during fold selection')
        if any(sha(Path(__file__).with_name(p)) != digest for p, digest in declaration['source_hashes'].items()):
            raise ValueError('Fold selection source changed during the run')
        (temp/'declaration.json').write_text(json.dumps(declaration, indent=2)+'\n')
        report = dict(parts=parts, counts=totals, research_ready=False,
                      binned_dataset_memory_verified=False)
        (temp/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        receipt(temp, dict(identity=identity(declaration), research_ready=False))
    return report


class FoldRows:
    """Random access with at most two open factorized shards; no dense full panel."""
    def __init__(self, path, split):
        if split not in ('train', 'validation'):
            raise ValueError('Explicit train or validation split required')
        self.path, self.split = Path(path), split
        doc = verify(self.path)
        declaration = json.loads((self.path/'declaration.json').read_text())
        if (declaration.get('schema') != 'v7-factorized-fold-v1'
                or declaration.get('feature_columns') != list(schema())
                or identity(declaration) != doc['identity']):
            raise ValueError('Fold declaration identity or schema differs')
        for filename, digest in declaration['inputs'].items():
            if sha(filename) != digest:
                raise ValueError('Selected source receipt changed')
        for filename, digest in declaration['source_hashes'].items():
            if sha(Path(__file__).with_name(filename)) != digest:
                raise ValueError('Fold selection source changed; rebuild required')
        report = json.loads((self.path/'report.json').read_text())
        self.parts = [p for p in report['parts'] if p[split]]
        self.ends = np.cumsum([p[split] for p in self.parts], dtype=np.int64)
        if not len(self.ends) or self.ends[-1] != report['counts'][split]:
            raise ValueError('Fold selection counts differ')
        self._load = lru_cache(maxsize=2)(self._load_part)

    def __len__(self):
        return int(self.ends[-1])

    def _load_part(self, number):
        part = self.parts[number]
        store = FactorizedRows(part['source'])
        indices = np.load(self.path/f"{part['ordinal']}-{self.split}-indices.npy", mmap_mode='r', allow_pickle=False)
        target = np.load(self.path/f"{part['ordinal']}-{self.split}-returns.npy", mmap_mode='r', allow_pickle=False)
        if (indices.dtype != np.dtype('int32') or indices.shape != (part[self.split],)
                or (indices < 0).any() or (indices >= len(store)).any()
                or (np.diff(indices) <= 0).any() or target.shape != indices.shape
                or target.dtype != np.dtype('float64') or not np.isfinite(target).all()):
            raise ValueError('Invalid fold row selection or labels')
        return store, indices, target

    def take(self, indices):
        indices = np.asarray(indices)
        if (indices.ndim != 1 or indices.dtype.kind not in 'iu' or len(indices) > MAX_ROWS
                or (indices < 0).any() or (indices >= len(self)).any()):
            raise ValueError('Bounded valid fold indices required')
        features = np.empty((len(indices), len(schema())), dtype=np.float32)
        labels = np.empty(len(indices), dtype=np.float64)
        groups = np.searchsorted(self.ends, indices, side='right')
        for group in np.unique(groups):
            store, selected, target = self._load(int(group))
            positions = np.flatnonzero(groups == group)
            local = indices[positions] - (self.ends[group-1] if group else 0)
            features[positions] = store.take(selected[local])
            labels[positions] = target[local]
        return features, labels

    def batches(self, batch_size=4096):
        if type(batch_size) is not int or not 1 <= batch_size <= MAX_ROWS:
            raise ValueError('Bounded positive batch size required')
        for start in range(0, len(self), batch_size):
            yield self.take(np.arange(start, min(start+batch_size, len(self)), dtype=np.int64))

    def lightgbm_sequence(self):
        import lightgbm as lgb
        rows = self

        class Sequence(lgb.Sequence):
            batch_size = 4096

            def __len__(self):
                return len(rows)

            def __getitem__(self, item):
                if isinstance(item, slice):
                    start, stop, step = item.indices(len(rows))
                    if len(range(start, stop, step)) > MAX_ROWS:
                        raise ValueError('Unbounded feature slice')
                    chosen = np.arange(start, stop, step, dtype=np.int64)
                    return rows.take(chosen)[0]
                if np.isscalar(item):
                    if not isinstance(item, (int, np.integer)):
                        raise ValueError('Integer feature row required')
                    return rows.take(np.array([item], dtype=np.int64))[0][0].astype(np.float64)
                return rows.take(np.asarray(item))[0]

        return Sequence()
