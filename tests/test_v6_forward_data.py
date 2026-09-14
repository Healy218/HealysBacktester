import unittest
import pandas as pd
from scripts.prepare_v6_forward_data import daily_frame_from_minutes
from v3.flatfiles import frame_from_minute_aggs
from v3.derive_contracts import daily_from_frame


class ForwardDataTests(unittest.TestCase):
    def test_direct_daily_matches_original_resample_then_daily_exactly(self):
        day=pd.Timestamp('2026-09-11')
        start=pd.Timestamp('2026-09-11 13:30Z').value
        rows=[]
        for ticker in ['O:SPY260918C00760000','O:SPY260918P00760000','O:QQQ260918P00500000']:
            for i in [0,2,14,15,30,121,389]:
                rows.append(dict(ticker=ticker,window_start=start+i*60000000000,
                    open=1+i/1000,high=2+i/1000,low=.5,close=1.5+i/1000,volume=i+1))
        raw=pd.DataFrame(rows).sample(frac=1,random_state=16)
        original=frame_from_minute_aggs(raw,{'SPY'})
        direct=daily_frame_from_minutes(raw,{'SPY'})
        spot={('SPY',day):760.}
        a,_=daily_from_frame(original,day,spot)
        b,_=daily_from_frame(direct,day,spot)
        pd.testing.assert_frame_equal(a,b,check_dtype=False)

    def test_fractional_option_volume_is_not_silently_truncated(self):
        raw=pd.DataFrame([dict(ticker='O:SPY260918C00760000',window_start=1,
            open=1,high=2,low=.5,close=1.5,volume=1.5)])
        with self.assertRaisesRegex(ValueError,'integral'): daily_frame_from_minutes(raw,{'SPY'})


if __name__=='__main__': unittest.main()
