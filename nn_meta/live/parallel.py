"""Parallel per-symbol DETECTION for the live scanners (2026-09-05).

A pass = load bars → detect fresh entries (per symbol, ~200–300 ms of
pandas/vectorbt) → score → alert. Detection is embarrassingly parallel and
dominates the pass once bars come from the stream store, so it runs in a
small process pool; scoring, dedupe, state and notification stay in the
parent, exactly as before. ``workers=1`` is the serial path (bit-identical).

Processes use the *spawn* start method: the parent may already have
TensorFlow loaded (the v4 bundle), and forking a TF process deadlocks.
Workers therefore re-import the light detection modules once per pass
(~2–3 s per worker) and reuse them across their chunk of symbols.

Worker count: ``SCAN_WORKERS`` env, else min(4, cpu_count). On the 8 GB
server keep the experts' totals ≤ ~8 concurrent workers (each ~300 MB).
"""
from __future__ import annotations
import concurrent.futures as cf
import multiprocessing as mp
import os
import traceback
from datetime import datetime
from typing import Callable, Iterable, Optional

from utils.logging_utils import setup_logging

logger = setup_logging(log_file="logs/backtester.log")


def default_workers() -> int:
    env = os.environ.get("SCAN_WORKERS")
    if env:
        try:
            return max(1, int(env))
        except ValueError:
            pass
    return max(1, min(4, os.cpu_count() or 1))


# ── worker entry points (top-level so spawn can import them by name) ─────────

def _v4_detect_one(sym: str, spec_entry: dict, strategies: list[str], now: datetime):
    """(closed bars, fresh proposals) for one symbol, using the real loader."""
    import pandas as pd                                          # noqa: F401
    from nn_meta.live.run_live import _bar_loader
    from nn_meta.live.scanner import aliased_bar_loader, closed_bars
    from nn_meta.live.v4_scan import fresh_proposals
    load = aliased_bar_loader(_bar_loader)
    bars = closed_bars(load(sym), now)
    return bars, fresh_proposals(sym, bars, spec_entry, strategies)


def _legacy_detect_one(sym: str, spec_entry: dict, now: datetime):
    """(closed bars, Signal-or-None) for one symbol, using the real loader."""
    from nn_meta.live.run_live import _bar_loader
    from nn_meta.live.scanner import (aliased_bar_loader, closed_bars,
                                      detect_fresh_signal)
    load = aliased_bar_loader(_bar_loader)
    bars = closed_bars(load(sym), now)
    return bars, detect_fresh_signal(sym, bars, spec_entry)


def _run_one(fn: Callable, sym: str, args: tuple):
    try:
        return sym, fn(sym, *args), None
    except Exception as exc:                                     # per-symbol isolation
        return sym, None, f"{exc.__class__.__name__}: {exc}\n{traceback.format_exc(limit=2)}"


def detect_many(fn: Callable, symbols: Iterable[str], args_for: Callable[[str], tuple],
                workers: int = 1) -> dict[str, tuple]:
    """Run ``fn(sym, *args_for(sym))`` for every symbol; returns
    {sym: (result, error)}. Serial when workers <= 1 (in-process, bit-identical
    to the old loops), else a spawn-context process pool."""
    symbols = list(symbols)
    out: dict[str, tuple] = {}
    if workers <= 1 or len(symbols) <= 1:
        for sym in symbols:
            _, res, err = _run_one(fn, sym, args_for(sym))
            out[sym] = (res, err)
        return out
    ctx = mp.get_context("spawn")
    with cf.ProcessPoolExecutor(max_workers=min(workers, len(symbols)), mp_context=ctx) as ex:
        futs = {ex.submit(_run_one, fn, sym, args_for(sym)): sym for sym in symbols}
        for fut in cf.as_completed(futs):
            sym = futs[fut]
            try:
                _, res, err = fut.result()
            except Exception as exc:                             # pool-level failure
                res, err = None, f"pool: {exc!r}"
            out[sym] = (res, err)
    return out
