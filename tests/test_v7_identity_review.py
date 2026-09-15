import json
import pytest
from nn_meta.v7.identity_review import reviewed_overrides
from nn_meta.v7.storage import receipt, sha


def setup(tmp_path):
    evidence = tmp_path / 'review.md'
    evidence.write_text('Reviewed fixture boundary')
    capture = tmp_path / 'ABC/2024-11-08'
    capture.mkdir(parents=True)
    (capture / 'response.json').write_text(json.dumps({'results': {'ticker': 'ABC'}}))
    receipt(capture, {'query': {'path': '/v3/reference/tickers/ABC', 'params': {'date': '2024-11-08'}}, 'http_status': 200})
    doc = {'schema': 'v7-reviewed-identity-boundaries-v1', 'evidence_path': str(evidence),
           'evidence_sha256': sha(evidence), 'resolutions': [{'root': 'ABC', 'anchor_month_end': '2024-10-31',
                'old_figi': 'old', 'dates': ['2024-11-08'], 'successor_first_trading_date': '2024-11-11'}]}
    path = tmp_path / 'declaration.json'
    path.write_text(json.dumps(doc))
    masters = {'2024-10-31': {'ABC': {'composite_figi': 'old'}}}
    return path, evidence, masters


def test_review_only_fills_missing_exact_dates_with_verified_old_anchor(tmp_path):
    path, evidence, masters = setup(tmp_path)
    result, sources = reviewed_overrides(path, masters=masters, reference_root=tmp_path, known={})
    assert result == {('ABC', '2024-11-08'): 'old'} and str(evidence) in sources
    with pytest.raises(ValueError, match='existing'):
        reviewed_overrides(path, masters=masters, reference_root=tmp_path, known={('ABC', '2024-11-08'): None})
    evidence.write_text('Changed')
    with pytest.raises(ValueError, match='evidence changed'):
        reviewed_overrides(path, masters=masters, reference_root=tmp_path, known={})


def test_wrong_anchor_or_outside_interval_cannot_resolve_an_identity(tmp_path):
    path, _, masters = setup(tmp_path)
    masters['2024-10-31']['ABC']['composite_figi'] = 'new'
    with pytest.raises(ValueError, match='monthly anchor'):
        reviewed_overrides(path, masters=masters, reference_root=tmp_path, known={})
    masters['2024-10-31']['ABC']['composite_figi'] = 'old'
    doc = json.loads(path.read_text())
    doc['resolutions'][0]['successor_first_trading_date'] = '2024-11-08'
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match='outside'):
        reviewed_overrides(path, masters=masters, reference_root=tmp_path, known={})
