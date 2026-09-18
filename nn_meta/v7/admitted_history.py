"""Consumer binding for explicitly admitted reconstructed action histories."""
import json
from pathlib import Path

import pandas as pd

from nn_meta.v7.action_coverage import require_history_coverage, validate_coverage_policy
from nn_meta.v7.storage import sha, verify


def bind_history_coverage(path, history, events, *, security_id, inputs):
    """Require every requested selected session and its exact compiled actions.

    The path is a source-bound coverage artifact, not a caller-supplied boolean.
    This does not admit option/stock holdings or full research readiness.
    """
    path = Path(path)
    doc = verify(path)
    dependencies = json.loads((path / 'inputs.json').read_text())
    dependencies.update({str(path / 'complete.json'): sha(path / 'complete.json')})
    dependencies.update({str(path / name): digest for name, digest in doc['files'].items()})
    for name, digest in dependencies.items():
        if sha(name) != digest or (name in inputs and inputs[name] != digest):
            raise ValueError('Action coverage source changed or conflicts with consuming history')
    policy = json.loads((path / 'policy.json').read_text())
    policy_id = validate_coverage_policy(policy)
    panel = pd.read_parquet(path / 'coverage.parquet', filters=[('security_id', '=', security_id)])
    required = history.source_date.tolist()
    selected = require_history_coverage(panel, security_id=security_id, dates=required)
    joined = history[['security_id', 'source_date', 'stock_ticker']].merge(
        selected[['security_id', 'source_date', 'stock_ticker']], on=['security_id','source_date'],
        validate='one_to_one', suffixes=('_history','_coverage'))
    if (not joined.stock_ticker_history.eq(joined.stock_ticker_coverage).all()
            or not selected.coverage_policy_identity.eq(policy_id).all()
            or selected.completeness_verified.any()):
        raise ValueError('Coverage policy or dated source identity differs from history')
    expected = {r['action']['event_id'] for r in events if r['security_id'] == security_id
                and pd.Timestamp(r['action']['effective_at']).tz_convert('America/New_York').date().isoformat() in set(required)}
    if set(selected.event_id.dropna()) != expected:
        raise ValueError('Consuming actions differ from admitted coverage')
    inputs.update(dependencies)
    return dict(schema='v7-consumed-action-coverage-v1', receipt_sha256=sha(path / 'complete.json'),
        policy_identity=policy_id, basis=policy['proposed_basis'], start=required[0], end=required[-1],
        sessions=len(required), security_id=security_id, completeness_verified=False,
        historical_publication_verified=False, held_position_admitted=False)
