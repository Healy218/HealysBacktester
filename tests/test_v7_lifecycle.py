import pandas as pd
import pytest
from nn_meta.v7.lifecycle import classify_gaps


def fixture():
    gap = dict(date='2023-05-03', membership_ticker='BBBY', security_id='old-company')
    event = dict(symbol='BBBY', security_id='old-company', first_session='2023-05-03',
                 last_session='2023-05-31', document_date='2023-05-02', kind='otc_successor',
                 successor='BBBYQ', source_url='https://example.org/notice',
                 point_in_time_admitted=False, held_positions_resolved=False)
    return gap, dict(schema='v7-reviewed-lifecycle-facts-v1', events=[event])


def test_lifecycle_review_never_resolves_execution_or_matches_reused_tickers():
    gap, review = fixture()
    rows = classify_gaps(pd.DataFrame([gap, {**gap, 'security_id': 'new-company'},
                                       {**gap, 'date': '2023-05-02'}]), review)
    assert [r['explanation'] for r in rows] == ['otc_successor', 'unexplained', 'unexplained']
    assert not any(r['point_in_time_admitted'] or r['held_positions_resolved'] for r in rows)


def test_conflicting_or_duplicate_session_evidence_fails_closed():
    gap, review = fixture()
    with pytest.raises(ValueError, match='Duplicate'):
        classify_gaps(pd.DataFrame([gap, gap]), review)
    review['events'] *= 2
    with pytest.raises(ValueError, match='Overlapping'):
        classify_gaps(pd.DataFrame([gap]), review)


def test_retrospective_fact_is_not_a_causal_execution_receipt():
    gap, review = fixture()
    review['events'][0]['point_in_time_admitted'] = True
    with pytest.raises(ValueError, match='cannot admit'):
        classify_gaps(pd.DataFrame([gap]), review)
