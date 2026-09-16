import pandas as pd
import pytest
from nn_meta.v7.exclusions import exclude_securities


def fixture():
    frame = pd.DataFrame([dict(month='2023-04', ticker=symbol, security_id=security, rank=rank, score=100-rank)
                         for symbol, security, rank in [('BBBY', 'old', 1), ('SPY', 'spy', 2), ('BBBY', 'new', 3)]])
    declaration = dict(schema='v7-user-universe-exclusions-v1', scope='entire_research_history',
        rerank_or_replace=False, historically_known_eligibility=False,
        exclusions=[dict(security_id='old', membership_tickers=['BBBY'])])
    return frame, declaration


def test_exclusions_bind_issuer_preserve_reused_ticker_and_do_not_backfill_ranks():
    frame, declaration = fixture()
    kept, removed = exclude_securities(frame, declaration)
    pd.testing.assert_frame_equal(kept, frame.iloc[1:])
    assert kept['rank'].tolist() == [2, 3] and removed.security_id.tolist() == ['old']


def test_exclusions_cannot_be_disguised_as_historical_information():
    frame, declaration = fixture()
    declaration['historically_known_eligibility'] = True
    with pytest.raises(ValueError, match='study restriction'):
        exclude_securities(frame, declaration)
    declaration['historically_known_eligibility'] = False
    declaration['exclusions'][0]['security_id'] = 'wrong-issuer'
    with pytest.raises(ValueError, match='identity/ticker'):
        exclude_securities(frame, declaration)
