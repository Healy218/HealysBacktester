import os
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

from v3 import pine_compat as pine
from v3.tv_sr_channels import support_resistance_channels
from v3.tv_uptrick import uptrick_adaptive_trend
from v3.tv_htf_log_profile import htf_log_regression_profile


class FastRecurrenceTests(unittest.TestCase):
    def both(self, function, *args, **kwargs):
        with patch.dict(os.environ, {'NN_META_V6_ACCELERATE':'0'}): slow=function(*args,**kwargs)
        with patch.dict(os.environ, {'NN_META_V6_ACCELERATE':'1'}): fast=function(*args,**kwargs)
        if isinstance(slow,pd.Series): pd.testing.assert_series_equal(slow,fast,check_exact=True)
        else: pd.testing.assert_frame_equal(slow,fast,check_exact=True)
    def bars(self,n=1200):
        rng=np.random.default_rng(339)
        close=100+np.cumsum(rng.normal(0,.1,n))
        opn=close+rng.normal(0,.05,n)
        return pd.DataFrame(dict(Open=opn,Close=close,High=np.maximum(opn,close)+rng.uniform(0,.1,n),
            Low=np.minimum(opn,close)-rng.uniform(0,.1,n),Volume=100.),index=pd.date_range('2026-01-01',periods=n,freq='15min'))
    def test_ema_rma_preserve_initialization_and_missing_observations_exactly(self):
        rng=np.random.default_rng(87); values=rng.normal(size=10000); values[::7]=np.nan
        for length in [1,2,14,50,200]:
            for function in [pine.ema,pine.rma]: self.both(function,pd.Series(values),length)
    def test_supertrend_scalar_and_variable_factors_match_every_bar(self):
        bars=self.bars().rename(columns=str.lower)
        for factor in [2.,pd.Series(np.linspace(1,3,len(bars)),index=bars.index)]: self.both(pine.supertrend,bars,factor,14)
    def test_channels_match_all_states_pivots_and_signals(self):
        bars=self.bars()
        for period in [4,10,30]:
            for source in ['High/Low','Close/Open']:
                self.both(support_resistance_channels,bars,pivot_period=period,pivot_source=source)
        bars.loc[:,['Open','High','Low','Close']]=100.
        self.both(support_resistance_channels,bars)
    def test_uptrick_preserves_counters_flips_and_numeric_features(self):
        self.both(uptrick_adaptive_trend,self.bars(n=4000))

    def test_sparse_htf_preserves_completed_sessions_and_partial_origin(self):
        bars=self.bars(n=230).tz_localize('UTC')
        for first in [False, True]:
            changes=pd.Series(False,index=bars.index)
            changes.iloc[[0,17,35,106,170,215]]=[first,True,True,True,True,True]
            full=htf_log_regression_profile(bars,changes,include_bins=True)
            for positions in [[0],[16,17,34,35,107,169,170,229],[229]]:
                got=htf_log_regression_profile(bars,changes,include_bins=True,observation_positions=positions)
                pd.testing.assert_frame_equal(full.iloc[positions],got,check_exact=True)


if __name__=='__main__': unittest.main()
