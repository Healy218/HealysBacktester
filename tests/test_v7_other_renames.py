from copy import deepcopy

import pandas as pd
import pytest

from nn_meta.v7.other_renames import unrelated_renames
from nn_meta.v7.storage import identity
from tests.test_v7_renames import inputs as rename_inputs


def inputs():
    rows,reviews,listings,history,cal=rename_inputs()
    for row in listings.values():
        row['composite_figi']='other';row['share_class_figi']='other-class'
    history['stock_ticker']='ABC';history=history.iloc[:1].copy()
    anchor={**listings['ABC','2024-09-12'],'composite_figi':'security','share_class_figi':'scoped-class'}
    # A historical scoped witness and the unrelated listing need distinct dates.
    history.loc[0,'source_date']='2024-09-16';listings['ABC','2024-09-16']=anchor
    review=dict(relationship='unrelated_ticker_reuse',effective_date='2024-09-13',
        record=reviews[0]['record'],evidence_identity='primary',rationale='Finite unrelated issuer review',
        prior_listing_sha256=identity(listings['ABC','2024-09-12']),
        effective_listing_sha256=identity(listings['XYZ','2024-09-13']),
        scoped_witness=dict(symbol='ABC',date='2024-09-16',security_id='security',record_sha256=identity(anchor)))
    return rows,[review],listings,history,cal


def test_unrelated_rename_keeps_original_reference_without_new_exclusion_or_price_action():
    args=inputs();events,pending=unrelated_renames(*args)
    assert not pending and len(events)==1
    assert events[0]['other_security_id']=='other'
    assert events[0]['replaces']==[args[1][0]['record']]
    assert 'action' not in events[0]


@pytest.mark.parametrize('change',['changed_record','changed_witness','different_legs','scoped_successor',
    'same_share_class','selected_leg','missing_listing','duplicate','no_primary'])
def test_unrelated_review_never_discards_a_scoped_successor_or_unbound_record(change):
    rows,reviews,listings,history,cal=deepcopy(inputs())
    if change=='changed_record':rows[0]['record']['new_symbol']='BAD'
    if change=='changed_witness':reviews[0]['scoped_witness']['record_sha256']='bad'
    if change=='different_legs':listings['XYZ','2024-09-13']['composite_figi']='different'
    if change=='scoped_successor':
        for key in [('ABC','2024-09-12'),('XYZ','2024-09-13')]:listings[key]['composite_figi']='security'
    if change=='same_share_class':listings['ABC','2024-09-16']['share_class_figi']='other-class'
    if change=='selected_leg':history.loc[0,'source_date']='2024-09-12'
    if change=='missing_listing':listings.pop(('ABC','2024-09-12'))
    if change=='duplicate':reviews*=2
    if change=='no_primary':reviews[0]['evidence_identity']=''
    with pytest.raises(ValueError):unrelated_renames(rows,reviews,listings,history,cal)
