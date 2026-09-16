"""Bounded train-only moments and exact disk-partitioned return quantiles."""
import json
from pathlib import Path

import numpy as np

from nn_meta.v7.factorized import MAX_ROWS
from nn_meta.v7.rows import schema
from nn_meta.v7.storage import identity, sha, receipt, transaction, verify
from nn_meta.v7.training_data import FoldRows

POLICY = 'v7-streamed-train-only-preprocessing-v1'


def merge_moments(count, mean, m2, block):
    """Chan combination with missing values excluded, float64 accumulators."""
    block = np.asarray(block, dtype=np.float64)
    if block.ndim != 2 or len(block) > MAX_ROWS or np.isinf(block).any():
        raise ValueError('Bounded finite-or-missing training features required')
    observed = np.isfinite(block)
    n = observed.sum(axis=0)
    total = np.where(observed, block, 0.).sum(axis=0)
    local_mean = np.divide(total, n, out=np.zeros_like(mean), where=n > 0)
    local_m2 = np.where(observed, block-local_mean, 0.) ** 2
    local_m2 = local_m2.sum(axis=0)
    combined = count+n
    delta = local_mean-mean
    fraction = np.divide(n, combined, out=np.zeros_like(mean), where=combined > 0)
    m2 = m2+local_m2+delta**2*count*fraction
    mean = mean+delta*fraction
    if not np.isfinite(mean).all() or not np.isfinite(m2).all():
        raise ValueError('Training moments overflowed')
    return combined, mean, m2


def fit_preprocessing(fold_path, output, *, batch_size=4096, quantiles=(.01, .99), weight_clip=1.,
                      reserve_bytes=100*1024**3):
    if (not 0 <= quantiles[0] < quantiles[1] <= 1
            or not np.isfinite(weight_clip) or weight_clip <= 0):
        raise ValueError('Ordered winsor quantiles and positive weight clip required')
    rows = FoldRows(fold_path, 'train')
    if type(reserve_bytes) is not int or reserve_bytes < 0:
        raise ValueError('Nonnegative declared disk reserve required')
    count = np.zeros(len(schema()), dtype=np.int64)
    mean = np.zeros(len(schema()), dtype=np.float64)
    m2 = np.zeros_like(mean)
    sources = {str(Path(fold_path)/'complete.json'): sha(Path(fold_path)/'complete.json'),
               str(Path(__file__)): sha(__file__)}
    if Path(output).exists():
        fitted = Preprocessor(output)
        expected = dict(sources=sources, rows=len(rows), batch_size=batch_size,
                        winsor_quantiles=list(quantiles), weight_clip=weight_clip, reserve_bytes=reserve_bytes)
        if any(fitted.report.get(key) != value for key, value in expected.items()):
            raise ValueError('Preprocessing resume settings differ')
        return fitted.report
    with transaction(output) as temp:
        import shutil
        if shutil.disk_usage(temp).free < reserve_bytes+len(rows)*8+1024**2:
            raise ValueError('Insufficient disk for exact targets and declared reserve')
        # Only returns are written densely. In-place selection has no full feature matrix.
        # Kept as inspectable sorted/partitioned target evidence, never used as row order.
        targets = np.lib.format.open_memmap(temp/'partitioned_train_returns.npy', mode='w+',
                                            dtype=np.float64, shape=(len(rows),))
        offset, weight_sum = 0, 0.
        for x, y in rows.batches(batch_size):
            count, mean, m2 = merge_moments(count, mean, m2, x)
            targets[offset:offset+len(y)] = y
            offset += len(y)
            weight_sum += np.minimum(np.abs(y), weight_clip).sum(dtype=np.float64)
        if offset != len(rows):
            raise ValueError('Training row count changed during preprocessing')
        points = np.asarray(quantiles, dtype=np.float64)*(len(rows)-1)
        lower, upper = np.floor(points).astype(np.int64), np.ceil(points).astype(np.int64)
        targets.partition(np.unique(np.r_[lower, upper]))
        bounds = targets[lower]+(targets[upper]-targets[lower])*(points-lower)
        targets.flush()
        del targets
        std = np.sqrt(np.divide(m2, count-1, out=np.ones_like(m2), where=count > 1))
        std[std == 0] = 1.
        report = dict(schema=POLICY, feature_columns=list(schema()), rows=len(rows),
            counts=count.tolist(), mean=mean.tolist(), std=std.tolist(),
            inactive=(count == 0).tolist(), winsor_quantiles=list(quantiles), winsor_bounds=bounds.tolist(),
            weight_clip=weight_clip, clipped_absolute_return_mean=weight_sum/len(rows),
            reserve_bytes=reserve_bytes, batch_size=batch_size,
            sources=sources, validation_used=False, research_ready=False)
        if any(sha(p) != digest for p, digest in sources.items()):
            raise ValueError('Training preprocessing input changed')
        (temp/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
        receipt(temp, dict(identity=identity(report), research_ready=False))
    return report


class Preprocessor:
    def __init__(self, path):
        path = Path(path)
        doc = verify(path)
        self.report = json.loads((path/'report.json').read_text())
        report = self.report
        if (report.get('schema') != POLICY or report.get('feature_columns') != list(schema())
                or identity(report) != doc['identity'] or report.get('validation_used') is not False):
            raise ValueError('Training preprocessing declaration differs')
        for source, digest in report['sources'].items():
            if sha(source) != digest:
                raise ValueError('Training preprocessing source changed')
        self.mean, self.std = np.asarray(report['mean']), np.asarray(report['std'])
        self.inactive = np.asarray(report['inactive'], dtype=bool)
        if (self.mean.shape != (len(schema()),) or self.std.shape != self.mean.shape
                or self.inactive.shape != self.mean.shape
                or not np.isfinite(self.mean).all() or not np.isfinite(self.std).all()
                or (self.std <= 0).any()):
            raise ValueError('Invalid training moments')

    def transform(self, block):
        block = np.asarray(block, dtype=np.float64)
        if (block.ndim != 2 or block.shape[1] != len(self.mean) or len(block) > MAX_ROWS
                or np.isinf(block).any()):
            raise ValueError('Bounded finite-or-missing feature batch required')
        result = (np.where(np.isnan(block), self.mean, block)-self.mean)/self.std
        result[:, self.inactive] = 0.
        with np.errstate(over='ignore', invalid='ignore'):
            result = result.astype(np.float32)
        if not np.isfinite(result).all():
            raise ValueError('Standardized feature overflow')
        return result

    def targets(self, returns, *, objective):
        values = np.asarray(returns, dtype=np.float64)
        if values.ndim != 1 or len(values) > MAX_ROWS or not np.isfinite(values).all():
            raise ValueError('Bounded finite target batch required')
        if objective == 'win':
            return (values > 0).astype(np.float32), np.ones(len(values), dtype=np.float32)
        if objective == 'weighted_win':
            denominator = self.report['clipped_absolute_return_mean']
            if denominator <= 0:
                raise ValueError('Return-weighted objective has zero training weight')
            weights = np.minimum(np.abs(values), self.report['weight_clip'])/denominator
            with np.errstate(over='ignore', invalid='ignore'):
                weights = weights.astype(np.float32)
            if not np.isfinite(weights).all():
                raise ValueError('Training weight overflow')
            return (values > 0).astype(np.float32), weights
        if objective == 'return_huber':
            with np.errstate(over='ignore', invalid='ignore'):
                target = np.clip(values, *self.report['winsor_bounds']).astype(np.float32)
            if not np.isfinite(target).all():
                raise ValueError('Training target overflow')
            return target, np.ones(len(values), dtype=np.float32)
        raise ValueError('Unregistered training objective')
