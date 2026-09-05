"""Parallel detection plumbing (2026-09-05): serial path unchanged, pool path
isolates per-symbol errors and returns every symbol."""
import os
from nn_meta.live import parallel


def _square(sym, k):
    if sym == "BAD":
        raise ValueError("boom")
    return len(sym) * k


def test_serial_and_pool_agree_and_isolate_errors():
    syms = ["SPY", "NVDA", "BAD", "PEP"]
    serial = parallel.detect_many(_square, syms, lambda s: (2,), workers=1)
    pool = parallel.detect_many(_square, syms, lambda s: (2,), workers=2)
    assert set(serial) == set(pool) == set(syms)
    for s in ("SPY", "NVDA", "PEP"):
        assert serial[s] == pool[s] == (len(s) * 2, None)
    assert serial["BAD"][0] is None and "boom" in serial["BAD"][1]
    assert pool["BAD"][0] is None and "boom" in pool["BAD"][1]


def test_default_workers_respects_env(monkeypatch):
    monkeypatch.setenv("SCAN_WORKERS", "3")
    assert parallel.default_workers() == 3
    monkeypatch.delenv("SCAN_WORKERS")
    assert 1 <= parallel.default_workers() <= 4
