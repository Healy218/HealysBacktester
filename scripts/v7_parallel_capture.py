"""Bounded concurrent I/O for the versioned entry campaign; original producers stay frozen."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import threading
import time

_POOL = None
_LOCAL = threading.local()
_STATS_LOCK = threading.Lock()
_STATS = dict(http_requests=0, http_seconds=0., response_bytes=0, retries=0, throttles=0)


def initialize(io_threads):
    global _POOL
    from nn_meta.v7.runtime import configure_threads
    from dotenv import load_dotenv
    from pathlib import Path
    configure_threads(1)
    load_dotenv(Path(__file__).resolve().parents[1]/'.env')
    _POOL = ThreadPoolExecutor(max_workers=io_threads)


def stats():
    with _STATS_LOCK:
        return dict(_STATS)


def client():
    """One persistent authenticated session per I/O thread; never share sessions."""
    if not hasattr(_LOCAL, 'client'):
        import requests
        from options.data.massive_ticks import MassiveTicks

        class Session(requests.Session):
            def get(self, *args, **kwargs):
                for attempt in range(4):
                    began = time.monotonic()
                    try:
                        response = super().get(*args, **kwargs)
                    except requests.RequestException:
                        if attempt == 3:
                            raise
                        with _STATS_LOCK:
                            _STATS['retries'] += 1
                        time.sleep(2**attempt)
                        continue
                    with _STATS_LOCK:
                        _STATS['http_requests'] += 1
                        _STATS['http_seconds'] += time.monotonic()-began
                        _STATS['response_bytes'] += len(response.content)
                        _STATS['throttles'] += int(response.status_code == 429)
                    # A paid-plan 429 needs investigation; do not hammer/retry it.
                    if response.status_code not in (500, 502, 503, 504) or attempt == 3:
                        return response
                    response.close()
                    with _STATS_LOCK:
                        _STATS['retries'] += 1
                    time.sleep(2**attempt)

        _LOCAL.client = MassiveTicks(session=Session())
    return _LOCAL.client


class SmallPageClient:
    def capture(self, **kwargs):
        # At most 20,000 rows per leaf before existing exact recursive splitting.
        # This bounds prefetched raw rows even when later symbols are very dense.
        return client().capture(**kwargs, page_size=5000)


def entries(items, failures, io_threads):
    """Prefetch at most one bounded leaf per active generator, in deterministic order."""
    from scripts.capture_v7_joined_sample import capture_split
    if _POOL is None:
        raise RuntimeError('Parallel capture worker was not initialized')
    remaining = iter(items)
    active = deque()
    def add():
        item = next(remaining, None)
        if item is not None:
            stream = capture_split(SmallPageClient(), item, failures)
            active.append((stream, _POOL.submit(next, stream, None)))
    for _ in range(io_threads):
        add()
    try:
        while active:
            stream, future = active.popleft()
            try:
                value = future.result()
                if value is None:
                    stream.close()
                    add()
                else:
                    yield value
                    del value
                    active.append((stream, _POOL.submit(next, stream, None)))
            finally:
                # The current stream must also close if the writer rejects a leaf.
                if not any(candidate is stream for candidate, _ in active):
                    stream.close()
    finally:
        # Drain before quota accounting so a failed pack cannot leave live fetches.
        for stream, future in active:
            future.cancel()
        for stream, future in active:
            try:
                future.result()
            except BaseException:
                pass
            stream.close()
