"""Resolve exact historical producer bytes without changing sealed artifacts.

Only the two reviewed September 18 cash-validator changes have snapshots.
Market data, declarations and every other producer retain strict current hashes.
"""
from pathlib import Path

from nn_meta.v7.storage import sha

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = {
    ('nn_meta/v7/stock_cash.py', 'fc02811a4c5f3f069555446932e594af967bc829876d3c596d835d6051dac301'):
        'nn_meta/v7/producer_snapshots/stock_cash_20260917.py',
    ('nn_meta/v7/stock_cash_dates.py', '465c2054beb3050a93143ac63eb32bde71c1cfbd6450295063a6d784743f11e0'):
        'nn_meta/v7/producer_snapshots/stock_cash_dates_20260917.py',
}


def historical_input_bindings(values):
    result = {}
    for name, digest in values.items():
        path = Path(name).resolve()
        relative = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else None
        snapshot = SNAPSHOTS.get((relative, digest))
        bound = str(ROOT / snapshot) if snapshot else name
        if sha(bound) != digest:
            raise ValueError('Historical input bytes differ; no registered producer snapshot')
        if bound in result and result[bound] != digest:
            raise ValueError('Conflicting historical input versions')
        result[bound] = digest
    return result
