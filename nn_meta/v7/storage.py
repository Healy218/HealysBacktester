"""Immutable bounded table/array stores for V7 performance comparisons."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import uuid

import numpy as np
import pyarrow as pa
import pyarrow.ipc as ipc
import pyarrow.parquet as pq


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


@contextmanager
def transaction(destination):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + '.partial-' + uuid.uuid4().hex)
    temporary.mkdir()
    yield temporary
    # Failed writes deliberately retain partial evidence and never create a receipt.
    for path in temporary.rglob('*'):
        if path.is_file():
            with path.open('rb') as stream:
                os.fsync(stream.fileno())
    temporary.rename(destination)
    fd = os.open(destination.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def receipt(root, metadata):
    files = {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*')) if p.is_file()}
    doc = {**metadata, 'files': files, 'complete': True}
    (root / 'complete.json').write_text(json.dumps(doc, sort_keys=True, indent=2, allow_nan=False) + '\n')


def verify(path, *, expected_identity=None):
    path = Path(path)
    doc = json.loads((path / 'complete.json').read_text())
    if doc.get('complete') is not True or not doc.get('files'):
        raise ValueError('Incomplete working store')
    if expected_identity is not None and doc.get('identity') != expected_identity:
        raise ValueError('Working-store input identity mismatch')
    for name, digest in doc['files'].items():
        part = Path(name)
        if part.is_absolute() or '..' in part.parts or sha(path / part) != digest:
            raise ValueError('Working-store integrity failure')
    return doc


def write_table(path, batches, *, schema, backend, input_identity):
    if backend not in ('parquet', 'arrow'):
        raise ValueError('Table backend must be parquet or arrow')
    count = 0
    with transaction(path) as temporary:
        target = temporary / ('data.parquet' if backend == 'parquet' else 'data.arrow')
        with target.open('wb') as stream:
            writer = (pq.ParquetWriter(stream, schema, compression='zstd') if backend == 'parquet'
                      else ipc.new_file(stream, schema, options=ipc.IpcWriteOptions(compression=None)))
            with writer:
                for batch in batches:
                    table = pa.Table.from_batches([batch]) if isinstance(batch, pa.RecordBatch) else batch
                    if not table.schema.equals(schema):
                        raise ValueError('Batch schema drift')
                    writer.write_table(table); count += table.num_rows
        receipt(temporary, {'backend': backend, 'rows': count, 'identity': input_identity,
                            'schema': str(schema), 'format': 'v7-working-table-v1'})


def table_batches(path, *, batch_size=65536):
    if batch_size < 1:
        raise ValueError('Positive batch size required')
    path = Path(path)
    doc = json.loads((path / 'complete.json').read_text())
    if doc['backend'] == 'parquet':
        yield from pq.ParquetFile(path / 'data.parquet').iter_batches(batch_size=batch_size)
    elif doc['backend'] == 'arrow':
        with pa.memory_map(str(path / 'data.arrow'), 'r') as source:
            reader = ipc.open_file(source)
            for i in range(reader.num_record_batches):
                batch = reader.get_batch(i)
                for offset in range(0, batch.num_rows, batch_size):
                    yield batch.slice(offset, batch_size)
    else:
        raise ValueError('Unsupported table store')


def write_matrix(path, batches, *, shape, dtype, backend, input_identity, chunk_rows=65536, columns=None):
    dtype = np.dtype(dtype)
    if backend not in ('numpy', 'zarr') or dtype.kind not in 'biuf' or len(shape) != 2 or min(shape) < 1 or chunk_rows < 1:
        raise ValueError('Expected a nonempty numerical matrix and numpy/zarr backend')
    if columns is not None and (len(columns) != shape[1] or len(set(columns)) != len(columns)):
        raise ValueError('Matrix columns must be unique and match its width')
    with transaction(path) as temporary:
        if backend == 'numpy':
            target = np.lib.format.open_memmap(temporary / 'data.npy', mode='w+', shape=shape, dtype=dtype)
        else:
            import zarr
            from numcodecs import Blosc
            target = zarr.open_array(str(temporary / 'data.zarr'), mode='w', shape=shape,
                chunks=(min(chunk_rows, shape[0]), min(32, shape[1])), dtype=dtype,
                compressor=Blosc(cname='zstd', clevel=1, shuffle=Blosc.BITSHUFFLE))
        offset = 0
        for batch in batches:
            batch = np.asarray(batch)
            if batch.dtype != dtype or batch.ndim != 2 or batch.shape[1] != shape[1] or offset + len(batch) > shape[0]:
                raise ValueError('Matrix shape/dtype drift')
            target[offset:offset + len(batch)] = batch; offset += len(batch)
        if offset != shape[0]:
            raise ValueError('Incomplete matrix')
        if backend == 'numpy':
            target.flush()
        del target
        receipt(temporary, {'backend': backend, 'shape': list(shape), 'dtype': dtype.str, 'columns': columns,
                            'identity': input_identity, 'format': 'v7-working-matrix-v1'})


def open_matrix(path, *, expected_identity=None):
    path = Path(path); doc = verify(path, expected_identity=expected_identity)
    if doc['backend'] == 'numpy':
        return np.load(path / 'data.npy', mmap_mode='r', allow_pickle=False)
    if doc['backend'] == 'zarr':
        import zarr
        return zarr.open_array(str(path / 'data.zarr'), mode='r')
    raise ValueError('Not a matrix store')
