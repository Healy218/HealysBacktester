import datetime as dt

import numpy as np

from nn_meta.etfe import dated_policy as d

STD=[{'type':'equity','symbol':'SPY','amount':'100','allocation_percentage':'100','settlement_type':'T+1'}]


def test_standard_and_zero_multiplier_resolve_from_deliverable():
    assert d.resolve_contract('SPY240119C00470000','100','100',STD)['reason']=='standard'
    r=d.resolve_contract('SPY240119C00470000','0','100',STD)
    assert r['status']=='admitted' and r['reason']=='deliverable_override_zero_multiplier' and r['multiplier']==100


def test_nonstandard_contracts_are_excluded():
    assert d.resolve_contract('1SPY240621P00370010','100','100',STD)['reason']=='nonstandard_symbol'
    odd=[dict(STD[0],amount='50')]
    assert d.resolve_contract('SPY240119C00470000','100','100',odd)['status']=='excluded'
    assert d.resolve_contract('SPY240119C00470000','100','100',STD+STD)['reason']=='multi_deliverable'
    assert d.resolve_contract('SPY240119C00470000','10','100',STD)['reason']=='multiplier_conflict'
    wrong=[dict(STD[0],symbol='QQQ')]
    assert d.resolve_contract('SPY240119C00470000','100','100',wrong)['status']=='excluded'


def test_regulatory_settlement_switches_on_trade_date():
    days=[dt.date(2024,5,d0) for d0 in (22,23,24,28,29,30,31)]
    assert d.regulatory_settlement(dt.date(2024,5,24),days)==dt.date(2024,5,29)  # T+2 over Memorial Day
    assert d.regulatory_settlement(dt.date(2024,5,28),days)==dt.date(2024,5,29)  # T+1
    assert d.regulatory_settlement(dt.date(2024,5,31),days) is None


def test_bank_holidays_skip_columbus_day():
    days=[dt.date(2024,10,d0) for d0 in (10,11,14,15)]
    assert dt.date(2024,10,14) in d.bank_holidays(2024)
    assert d.regulatory_settlement(dt.date(2024,10,11),days)==dt.date(2024,10,15)
    assert d.bank_holidays(2023)=={dt.date(2023,10,9)}  # Veterans Day on Saturday is not observed


def test_action_known_from_next_session():
    days=[dt.date(2024,3,d0) for d0 in (13,14,15,18)]
    assert d.known_from_session(dt.date(2024,3,14),days)==dt.date(2024,3,15)
    assert d.known_from_session(dt.date(2024,3,16),days)==dt.date(2024,3,18)
    assert d.known_from_session(dt.date(2024,3,18),days) is None


def test_contract_available_requires_prior_observation():
    assert d.contract_available(100,100) and not d.contract_available(101,100)
    assert not d.contract_available(None,100)


def test_rewarm_mask_excludes_bars_after_each_gap_without_filling():
    bars=np.array([0,1,2,4,5,6,7,9,10])
    mask=d.rewarm_mask(bars,[3,8],2)
    assert mask.tolist()==[False,False,False,True,True,False,False,True,True]
    assert d.rewarm_mask(bars,[],5).sum()==0


def test_quote_size_switches_from_lots_to_shares():
    assert d.quote_size_shares('3',dt.date(2025,10,31))==300
    assert d.quote_size_shares('240',dt.date(2025,11,3))==240
    assert d.quote_size_shares(0,dt.date(2024,1,19))==0
