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
        # One full provider page (50,000 rows) per leaf. Avoid redundant small-page
        # round trips while bounding prefetched data before exact recursive splitting.
        kwargs["max_pages"] = 1
        return client().capture(**kwargs, page_size=50000)


def prefetch_limit(io_threads):
    """Reduce raw-row buffers before the service approaches its 14 GiB ceiling."""
    from pathlib import Path
    try:
        relative=next(line.split(':',2)[2] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
        used=int((Path('/sys/fs/cgroup')/relative.lstrip('/')/'memory.current').read_text())
    except (OSError,StopIteration,ValueError):
        return min(io_threads,16)
    gib=1024**3
    ceiling=2 if used>=10*gib else 8 if used>=8*gib else 16 if used>=6*gib else 32
    return min(io_threads,ceiling)


def entries(items, failures, io_threads):
    """Bounded raw-leaf prefetch; consume buffers before scheduling more under pressure."""
    from scripts.capture_v7_joined_sample import capture_split
    if _POOL is None:raise RuntimeError('Parallel worker was not initialized')
    remaining=iter(items);active=deque();parked=deque();exhausted=False
    def fill():
        nonlocal exhausted
        while len(active)<prefetch_limit(io_threads):
            if parked:stream=parked.popleft()
            elif not exhausted:
                item=next(remaining,None)
                if item is None:exhausted=True;break
                stream=capture_split(SmallPageClient(),item,failures)
            else:break
            active.append((stream,_POOL.submit(next,stream,None)))
    fill()
    try:
        while active or parked or not exhausted:
            if not active:fill()
            if not active:break
            stream,future=active.popleft()
            try:
                value=future.result()
                if value is not None:
                    yield value
                    del value
                    parked.append(stream)
                else:stream.close()
            finally:
                if not any(candidate is stream for candidate in parked):stream.close()
            fill()
    finally:
        for stream,future in active:future.cancel()
        for stream,future in active:
            try:future.result()
            except BaseException:pass
            stream.close()
        for stream in parked:stream.close()
