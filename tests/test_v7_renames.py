from copy import deepcopy
import json
from pathlib import Path

import pandas as pd
import pytest

from nn_meta.v7.action_coverage import coverage_panel
from nn_meta.v7.renames import compile_renames
from nn_meta.v7.storage import identity
from tests.test_v7_ordinary_actions import fixture, make_candidate


def inputs():
    _, _, history, cal, _ = fixture()
    history['source_status'] = 'observed'; history.loc[1, 'stock_ticker'] = 'XYZ'
    row = make_candidate('alpaca', 'name_changes', dict(id='rename', old_symbol='ABC',
        new_symbol='XYZ', old_cusip='111', new_cusip='111', process_date='2024-09-16'))
    listing = dict(active=True, composite_figi='security', share_class_figi='share-class',
        type='CS', locale='us', market='stocks', currency_name='usd', primary_exchange='XNYS', cik='issuer')
    # The retained full-market capture supports XNYS through its configured exchange set.
    from nn_meta.v7.daily_identities import EXCHANGES
    listing['primary_exchange'] = EXCHANGES[0]
    before={**listing,'ticker':'ABC'}; after={**listing,'ticker':'XYZ'}
    review=dict(conclusion='unchanged_common_shares_ticker_change',effective_date='2024-09-13',
        security_id='security',share_class_figi='share-class',evidence_identity='primary-notice',
        publication_available_ns=int(pd.Timestamp('2024-09-11T04:00Z').value),
        prior_listing_sha256=identity(before),effective_listing_sha256=identity(after),
        record={k:row[k] for k in ['provider','kind','action_id','record_sha256']})
    return [row],[review],{('ABC','2024-09-12'):before,('XYZ','2024-09-13'):after},history,cal


def test_review_clears_only_its_record_preserves_identity_and_adds_no_price_factor():
    args=inputs(); events,pending=compile_renames(*args)
    policy=json.loads((Path(__file__).resolve().parents[1]/'docs/specs/V7_NO_EVENT_ADMISSION_20260917.json').read_text())
    prior=coverage_panel(args[3],args[0],[],args[0],policy=policy)
    assert not prior.history_admitted.any()
    panel=coverage_panel(args[3],args[0],[],pending,policy=policy,renames=events)
    assert panel.history_admitted.all() and panel.event_id.isna().all()
    assert panel.identity_event_id.dropna().tolist()==[events[0]['event_id']]
    assert events[0]['effective_date']=='2024-09-13'  # Not the provider's process date.
    complex_row=make_candidate('alpaca','spin_offs',dict(id='spin',source_symbol='ABC',ex_date='2024-09-13'))
    complex_row['scoped_symbols']=['XYZ']
    blocked=coverage_panel(args[3],args[0]+[complex_row],[],[complex_row],policy=policy,renames=events)
    assert blocked.history_admitted.tolist()==[True,False]
    assert not panel.held_position_admitted.any()


@pytest.mark.parametrize('change',['share_class','security','late_notice','wrong_original','bad_original',
    'missing_listing','different_issuer','duplicate','wrong_history','wrong_clock','missing_continuity'])
def test_unknown_changed_or_conflicting_rename_evidence_is_rejected(change):
    rows,reviews,listings,history,cal=deepcopy(inputs());review=reviews[0]
    if change=='share_class':listings['XYZ','2024-09-13']['share_class_figi']='different'
    if change=='security':review['security_id']='different'
    if change=='late_notice':review['publication_available_ns']=int(pd.Timestamp('2024-09-14T00:00Z').value)
    if change=='wrong_original':review['record']['record_sha256']='changed'
    if change=='bad_original':rows[0]['record']['new_symbol']='different'
    if change=='missing_listing':listings.pop(('ABC','2024-09-12'))
    if change=='different_issuer':listings['XYZ','2024-09-13']['cik']='different'
    if change=='duplicate':reviews*=2
    if change=='wrong_history':history.loc[0,'stock_ticker']='different'
    if change=='wrong_clock':history.loc[1,'session_open_ns']+=1
    if change=='missing_continuity':history.loc[0,'identity_span']='different'
    with pytest.raises(ValueError):compile_renames(rows,reviews,listings,history,cal)
