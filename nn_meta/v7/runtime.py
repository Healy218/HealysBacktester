"""Explicit outer-worker/inner-thread controls. No allocator or kernel overrides."""
from __future__ import annotations

import os
import sys
from concurrent.futures import ProcessPoolExecutor
import multiprocessing


def configure_threads(threads=1):
    if type(threads) is not int or not 1 <= threads <= 4:
        raise ValueError('Inner threads must be 1–4')
    if 'polars' in sys.modules and sys.modules['polars'].thread_pool_size() > threads:
        raise RuntimeError('Polars was initialized before thread limits; use a fresh spawned process')
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                 'NUMBA_NUM_THREADS', 'POLARS_MAX_THREADS', 'BLOSC_NTHREADS'):
        os.environ[name] = str(threads)
    import pyarrow as pa
    from numcodecs import blosc
    from threadpoolctl import threadpool_limits
    pa.set_cpu_count(threads); pa.set_io_thread_count(threads)
    blosc.set_nthreads(threads)
    threadpool_limits(limits=threads)
    return {'arrow_cpu_threads': pa.cpu_count(), 'arrow_io_threads': pa.io_thread_count(),
            'blosc_threads': blosc.get_nthreads(), 'polars_max_threads': os.environ['POLARS_MAX_THREADS'],
            'arrow_allocator': pa.default_memory_pool().backend_name,
            'process_start_method': 'spawn'}


def worker_pool(workers, *, threads=1):
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError('V7 permits 1–4 outer workers')
    configure_threads(threads)
    return ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'),
                               initializer=configure_threads, initargs=(threads,))
