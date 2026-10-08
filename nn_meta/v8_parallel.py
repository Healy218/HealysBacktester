# nn_meta/v8_parallel.py — worker sizing and shared rate limiting for V8 jobs.
"""Python counterpart of scripts/lib/autosize.sh plus a thread-safe rate
limiter for the Alpaca free tier (200 requests/minute per account).

autosize_workers sizes against MemAvailable (never swap: most of it is zram
on this box), floored at 1 and capped at the CPU count, exactly like the
shell helper, and returns the reason string for the run log.
"""
from __future__ import annotations

import os
import threading
import time


def mem_available_mb() -> int:
    with open("/proc/meminfo") as f:
        for line in f:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    raise RuntimeError("MemAvailable missing from /proc/meminfo")


def autosize_workers(per_worker_mb: int, reserve_mb: int = 2048,
                     cap: int | None = None) -> tuple[int, str]:
    avail = mem_available_mb()
    cpus = os.cpu_count() or 1
    n = max(1, min((avail - reserve_mb) // per_worker_mb, cpus))
    if cap is not None:
        n = max(1, min(n, cap))
    why = (f"{n} workers (MemAvailable {avail / 1024:.1f}GB, "
           f"{per_worker_mb}MB/worker, {cpus} threads"
           + (f", cap {cap}" if cap is not None else "") + ")")
    return n, why


class RateLimiter:
    """At most `per_minute` acquisitions per rolling minute, evenly spaced,
    shared by every thread holding this instance."""

    def __init__(self, per_minute: float):
        self.interval = 60.0 / per_minute
        self._next = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next)
            self._next = slot + self.interval
        delay = slot - time.monotonic()
        if delay > 0:
            time.sleep(delay)
