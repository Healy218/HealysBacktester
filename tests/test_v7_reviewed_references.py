from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from nn_meta.v7.reviewed_references import corrected_terms,ReviewedContractReferences

C='GAP240830C00025000';D='2024-08-23'


def evidence():
    body=dict(status='OK',results=dict(ticker='O:'+C,underlying_ticker='GPS',expiration_date='2024-08-30',
        contract_type='call',strike_price=25,shares_per_contract=100,exercise_style='american',primary_exchange='BATO'))
    review=dict(contract=C,date=D,old_symbol='GPS',new_symbol='GAP',published_date='2024-08-21',effective_date='2024-08-22')
    return body,review


def test_normalizes_only_underlying_and_preserves_original_evidence():
    body,review=evidence();original=deepcopy(body)
    result=corrected_terms(C,D,body,200,'original-anchor',review)
    assert result['underlying']=='GAP' and result['provider_underlying']=='GPS'
    assert result['metadata_receipt_sha256']=='original-anchor' and body==original


@pytest.mark.parametrize('change',[
    {'additional_underlyings':[{'type':'currency','underlying':'USD','amount':1442.76}]},
    {'shares_per_contract':150},{'strike_price':26},{'ticker':'O:WRONG'},
])
def test_rename_never_admits_other_invalid_or_adjusted_terms(change):
    body,review=evidence();body['results'].update(change)
    with pytest.raises(ValueError,match='standard'):corrected_terms(C,D,body,200,'anchor',review)


def test_exact_date_and_publication_scope_remain_mandatory():
    body,review=evidence()
    with pytest.raises(ValueError,match='scope'):corrected_terms(C,'2024-08-26',body,200,'anchor',review)
    review['published_date']='2024-08-23'
    with pytest.raises(ValueError,match='scope'):corrected_terms(C,D,body,200,'anchor',review)


def test_missing_reference_cannot_be_repaired_by_rename():
    body,review=evidence()
    with pytest.raises(ValueError,match='unavailable'):corrected_terms(C,D,body,404,'anchor',review)
