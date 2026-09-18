from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import pandas as pd
import pytest
from nn_meta.v7.dividend_finalization import final_dividend_audit
from nn_meta.v7.dividend_resolution import compile_dividend_resolutions
from nn_meta.v7.storage import identity
from tests.test_v7_dividend_resolution import case


def inputs():
    args=case();actions,cash,pending=compile_dividend_resolutions(*args)
    history=args[2].copy();history['source_status']='observed';history['dividend_boundary_only']=False
    schedule=SimpleNamespace(document=dict(coverage_start=args[3].start,coverage_end=args[3].end))
    policy=json.loads((Path(__file__).resolve().parents[1]/'docs/specs/V7_NO_EVENT_ADMISSION_20260917.json').read_text())
    return [args[0],actions,cash,pending,[],[],history,history.copy(),[],args[3],schedule,policy]


def test_full_dividend_census_closes_without_admitting_held_lifecycle():
    report,coverage,aux,checks=final_dividend_audit(*inputs())
    assert report['dividends_complete'] and report['remaining_dividend_review_items']==0
    assert report['total_cash_payments']==2 and report['verified_cash_price_boundaries']==1
    assert not report['step_1_complete'] and not report['research_ready']
    assert not coverage.held_position_admitted.any() and not aux


def test_legacy_action_date_comes_from_its_verified_effective_clock():
    args=inputs();args[1][0].pop('effective_date')
    for e in args[2]:
        e['source_identity']=identity(args[1][0]);e['event_id']='stock-cash:'+identity({k:v for k,v in e.items() if k!='event_id'})
    assert final_dividend_audit(*args)[0]['dividends_complete']


@pytest.mark.parametrize('change',['missing_leaf','unresolved_cash','changed_factor','changed_price','lost_boundary','changed_original'])
def test_finalization_rejects_incomplete_or_inconsistent_consumers(change):
    args=inputs()
    if change=='missing_leaf':args[2].pop()
    elif change=='unresolved_cash':args[3]=deepcopy(args[0]);args[1]=[];args[2]=[]
    elif change=='changed_factor':
        args[1][0]['action']['price_factor']=.8
        for e in args[2]:
            e['source_identity']=identity(args[1][0]);e['event_id']='stock-cash:'+identity({k:v for k,v in e.items() if k!='event_id'})
    elif change=='changed_price':args[7].loc[0,'raw_close']=101.
    elif change=='lost_boundary':args[7]=args[7].iloc[1:]
    else:args[0][0]['record']['cash_amount']=4
    with pytest.raises(ValueError):final_dividend_audit(*args)


def test_auxiliary_cash_does_not_expand_canonical_coverage():
    args=inputs();args[6]['security_id']='predecessor'
    args[7]['dividend_boundary_only']=True
    args[8]=[dict(security_id='sid',ex_date='2024-06-12',source_symbol='ABC',
                  changes_trading_eligibility=False,bridges_reorganization=False)]
    report,coverage,aux,checks=final_dividend_audit(*args)
    assert report['dividends_complete'] and len(aux)==1
    assert coverage.security_id.unique().tolist()==['predecessor']
    assert coverage.event_id.isna().all() and len(coverage)==len(args[6])
    args[8][0]['bridges_reorganization']=True
    with pytest.raises(ValueError):final_dividend_audit(*args)
