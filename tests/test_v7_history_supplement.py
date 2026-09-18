import pandas as pd
import pytest

from nn_meta.v7.history_supplement import supplement_history
from nn_meta.v7.security_history import security_history
from tests.test_v7_security_history import fixture


def inputs():
    stock, clock = fixture()
    original = security_history(stock.drop(index=2), clock, security_id='security')
    original['provider_composite_figi'] = original.security_id.where(original.stock_ticker.notna()).astype('string')
    original['identity_resolution'] = 'original_selected_identity'
    original['identity_resolution_evidence'] = pd.Series(pd.NA, index=original.index, dtype='string')
    original['resolved_share_class_figi'] = pd.Series(pd.NA, index=original.index, dtype='string')
    return original, stock.loc[[2]], stock, clock


def test_additive_supplement_restores_only_observed_exact_identity_without_changing_prefix():
    original, incoming, stock, clock = inputs()
    original.loc[0, 'listed_source_candidates'] = 2
    original.loc[0, 'source_selection_evidence'] = 'retained-route-review'
    result = supplement_history(original, incoming, security_id='security', evidence_identity='bound')
    pd.testing.assert_frame_equal(result.iloc[:2][original.columns[:-4]], original.iloc[:2][original.columns[:-4]])
    assert result.raw_close.tolist() == [100., 101., 102., 103.]
    assert result.identity_span.nunique() == 1
    assert result.identity_resolution.iloc[2] == 'supplemented_exact_day_identity'
    assert result.identity_resolution_evidence.iloc[2] == 'bound'
    assert original.stock_ticker.isna().sum() == 1


@pytest.mark.parametrize('change', ['replace', 'wrong_id', 'duplicate', 'outside', 'missing_evidence'])
def test_supplement_cannot_overwrite_known_sources_or_invent_identity(change):
    original, incoming, stock, clock = inputs(); evidence='bound'
    if change == 'replace': incoming = stock.loc[[0]]
    if change == 'wrong_id': incoming.loc[:, 'listed_security_id'] = 'different'
    if change == 'duplicate': incoming = pd.concat([incoming, incoming])
    if change == 'outside': incoming.loc[:, 'source_date'] = '2026-01-01'
    if change == 'missing_evidence': evidence = ''
    with pytest.raises(ValueError): supplement_history(original, incoming, security_id='security', evidence_identity=evidence)
