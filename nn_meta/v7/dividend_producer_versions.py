"""Retain the exact pre-primary-dividend action loader alongside prior snapshots."""
from pathlib import Path

from nn_meta.v7.producer_versions import SNAPSHOTS as CASH_SNAPSHOTS, ROOT
from nn_meta.v7.storage import sha

SNAPSHOTS = dict(CASH_SNAPSHOTS)
SNAPSHOTS[('nn_meta/v7/ordinary_actions.py',
    '99a1baa2e49207de008be988e02f417bc0001dd4b3692de8754224c311a08ab0')] = (
    'nn_meta/v7/producer_snapshots/ordinary_actions_20260918.py')


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

