import pytest

from options.paper_risk import (V6_OPTION_RISK, V7_OPTION_RISK, premium_stop,
                                in_the_money, strategy_only_simulator_config)


@pytest.mark.parametrize('policy,threshold', [(V6_OPTION_RISK,3.7),(V7_OPTION_RISK,3.5)])
def test_option_premium_threshold_uses_fixed_entry_midpoint(policy, threshold):
    assert not premium_stop(4.,threshold+.000001,policy)['triggered']
    assert premium_stop(4.,threshold,policy)['triggered']
    assert premium_stop(4.,threshold-.000001,policy)['triggered']
    assert not premium_stop(4.,4.,policy)['triggered']
    assert premium_stop(4.,0.,policy)['triggered']
    assert not premium_stop(4.,8.,policy)['triggered']


@pytest.mark.parametrize('entry,current', [(0.,1.),(1.,-1.),(float('nan'),1.),(1.,float('inf')),(True,1.)])
def test_invalid_premium_references_are_rejected(entry,current):
    with pytest.raises(ValueError):premium_stop(entry,current,V7_OPTION_RISK)


def test_calls_puts_and_at_money_expiry_classification():
    assert in_the_money('C',100.,100.01)
    assert not in_the_money('C',100.,100.)
    assert in_the_money('P',100.,99.99)
    assert not in_the_money('P',100.,100.)
    with pytest.raises(ValueError):in_the_money('C',100.,float('nan'))


def test_execution_amendment_does_not_change_frozen_global_simulator_config():
    from nn_meta.config import SIM_CONFIG
    from copy import deepcopy
    from utils.runner_utils import sim_kwargs
    before=deepcopy(SIM_CONFIG)
    new=strategy_only_simulator_config(SIM_CONFIG)
    assert new['USE_STOP_LOSS'] is False and sim_kwargs(new)['sl_stop'] is None
    assert SIM_CONFIG==before and SIM_CONFIG['USE_STOP_LOSS'] is True
    assert new['TREND_FILTER_WINDOW']==before['TREND_FILTER_WINDOW']
