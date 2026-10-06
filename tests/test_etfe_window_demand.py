import pandas as pd
import pytest
from nn_meta.etfe.window_demand import context_jobs,reference_windows,holding_frontier,MINUTE


def test_context_all_strikes_and_rights_preserve_adjusted_and_exclude_zero_dte():
    contracts={s:dict(underlying_symbol='SPY',expiration_date=e) for s,e in [('call','2024-01-19'),('put','2024-01-19'),('1SPY','2024-03-02'),('expired','2024-01-18'),('far','2024-03-04')]}
    rows=list(context_jobs(contracts,[dict(date='2024-01-18',open='09:30',close='13:00')]))
    assert len(rows)==1 and rows[0]['symbols']==['1SPY','call','put']
    assert rows[0]['end_exclusive_ns']-rows[0]['start_ns']==210*MINUTE
    assert not rows[0]['historical_eligibility_admitted']


def test_context_batches_have_exact_membership_and_no_duplicates():
    contracts={str(i):dict(underlying_symbol='VOO',expiration_date='2024-01-19') for i in range(205)}
    rows=list(context_jobs(contracts,[dict(date='2024-01-18',open='09:30',close='16:00')]))
    assert [len(r['symbols']) for r in rows]==[100,100,5]
    assert sorted(s for r in rows for s in r['symbols'])==sorted(contracts)


def test_feature_and_entry_windows_have_distinct_causal_ends():
    r=reference_windows(20*MINUTE,5,0,390*MINUTE)
    assert r['feature']==(14*MINUTE,19*MINUTE) and r['entry']==(19*MINUTE,20*MINUTE)
    assert reference_windows(5*MINUTE,5,0,390*MINUTE)['feature'] is None
    with pytest.raises(ValueError):reference_windows(391*MINUTE,1,0,390*MINUTE)


def state(kind):return dict(kind=kind,contract='option',ticker='SPY',ledger_receipt_sha256='a'*64)

def frontier(kind,at,session=(0,390*MINUTE),cutoff=375*MINUTE,end=1000*MINUTE):
    return holding_frontier(state(kind),at,session=session,cutoff_ns=cutoff,end_ns=end)


def test_holding_requires_previous_completed_bar_and_fresh_expiry_quote():
    r=frontier('option_held',20*MINUTE)
    assert r['requests']==[dict(route='option_bars',symbol='option',start_ns=18*MINUTE,end_exclusive_ns=19*MINUTE)]
    r=frontier('exit_pending',375*MINUTE+10**9)
    assert r['requests'][0]['end_exclusive_ns']==375*MINUTE
    assert r['requests'][1]['route']=='stock_quotes'
    assert r['requests'][1]['end_exclusive_ns']==375*MINUTE+10**9+1


def test_roll_stock_and_official_close_are_separate_inputs():
    for kind in ('roll_pending','stock_held','stock_exit_pending'):
        assert frontier(kind,MINUTE)['requests'][0]['route']=='stock_quotes'
    assert frontier('exercise_pending',390*MINUTE)['requests'][0]['route']=='official_exercise_reference'
    assert frontier('settlement_pending',500*MINUTE)['disposition']=='await_dated_settlement'


def test_missing_clocks_and_end_never_fake_a_terminal_exit():
    assert frontier('option_held',MINUTE,session=None)['disposition']=='dated_session_unresolved'
    assert frontier('option_held',MINUTE,cutoff=None)['disposition']=='dated_expiry_cutoff_unresolved'
    assert frontier('option_held',1000*MINUTE)['disposition']=='right_censored_end'
    with pytest.raises(ValueError,match='Ledger evidence'):
        holding_frontier({},0,session=None,cutoff_ns=None,end_ns=MINUTE)
