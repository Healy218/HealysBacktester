from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import date
import json
import pandas as pd
from options.execution import Execution
from nn_meta import config
from nn_meta import build_meta_dataset as bm
from nn_meta.download_universe import compact_bars_daily
from nn_meta.spx0.contracts import pick_wing, parse_occ

with TemporaryDirectory() as tmp:
    p=Path(tmp)/'bars_daily'; p.mkdir()
    for n,d in enumerate(['2025-01-02','2025-03-03']):
        pd.DataFrame({'ticker':['O:SPY250321C00600000'],'date':pd.to_datetime([d]),'close':[2.0]}).to_parquet(p/f'bars_part_{n}.parquet')
    config.BARS_DAILY_DIR=p
    compact_bars_daily()
    print('COMPACTION remaining dates',pd.concat([pd.read_parquet(f) for f in p.glob('*.parquet')])['date'].tolist())

class Provider:
    def get_contract_bars(self,occ,start,end,interval):
        return pd.DataFrame({'Close':[1.,2.,3.]},index=pd.to_datetime(['2025-01-02','2025-01-03','2025-01-06'])).loc[start:end]
e=Execution('SPY','15m','2025-02-01',Provider(),{})
e.bars('X',date(2025,1,6),date(2025,1,6))
print('CACHE expanded request starts', e.bars('X',date(2025,1,2),date(2025,1,6)).index.min())

with TemporaryDirectory() as tmp:
    config.ROOT=Path(tmp)
    p=config.ROOT/'artifacts_v5'; (p/'meta_rows').mkdir(parents=True)
    entry={'strategies':{'ma':{'params':{'fast_window':2,'slow_window':4},'dte':5}}}
    (p/'baseline_spec.json').write_text(json.dumps({'symbols':{'SPY':entry},'dte_grid':[1,5,10,30,45]}))
    pd.DataFrame({'strategy':['ma']*5,'dte':[1,5,10,30,45]}).to_parquet(p/'meta_rows'/'SPY.parquet')
    config.WEEKLY_DTE_ENABLED=True
    rows,marks=bm._reusable_rows('SPY',entry,'v5',True)
    print('REUSE weekly unchanged winner rows dtes',rows.dte.tolist(),'marks',marks)

at=pd.Timestamp('2025-06-10 14:00')
def row(k,t):
    return {'occ':f'SPXW250610P{int(k*1000):08d}','index':'SPX','right':'P','strike':k,'timestamp':t}
# At decision there are 10-point gaps; later prints halve the measured grid.
past=pd.DataFrame([row(k,at-pd.Timedelta(minutes=1)) for k in [5970,5980,5990,6000,6010]])
future=pd.DataFrame([row(k,at+pd.Timedelta(hours=1)) for k in [5975,5985,5995,6005]])
short=parse_occ('SPXW250610P06000000')
for name,frame in [('past',past),('full day',pd.concat([past,future],ignore_index=True))]:
    wing=pick_wing(frame,short_leg=short,mapped_spot=6000,wing_strikes=2,at=at)
    print('WING',name,wing.strike)
from nn_meta.universe_pit import load_daily_rows, write_membership_parquet, monthly_membership
with TemporaryDirectory() as tmp:
    p=Path(tmp)
    pd.DataFrame({'root':['SPY']*3,'date':pd.to_datetime(['2025-01-29','2025-01-30','2025-01-31']),'opt_dollar_vol':[100]*3}).to_parquet(p/'2025-01.parquet')
    membership=monthly_membership(load_daily_rows(p),window_days=2,min_active_days=1)
    write_membership_parquet(membership,p)
    try:
        monthly_membership(load_daily_rows(p),window_days=2,min_active_days=1)
    except Exception as e:
        print('PIT SECOND RUN',type(e).__name__,str(e))
from tests.test_execution import SyntheticProvider,DAYS,_underlying
from options.execution import execute_trade_returns
prov=SyntheticProvider(DAYS,['2025-06-06','2025-06-13'])
close,idx=_underlying()
trades=[(idx[0],idx[51],0),(idx[130],idx[181],0)]
shared=Execution('SPY','15m','2025-06-30',prov,{})
execute_trade_returns(shared,trades,close,idx,1)
r,_=execute_trade_returns(shared,trades,close,idx,10)
fresh,_=execute_trade_returns(Execution('SPY','15m','2025-06-30',prov,{}),trades,close,idx,10)
print('DTE SWEEP shared vs fresh first-trade executed',r[0]['executed'],fresh[0]['executed'])
from nn_meta.spx0.build_dataset import _stop_target_ts
from nn_meta.spx0.fills import exit_fill,DepthPolicy
from nn_meta.spx0.config import TradeVariant
b=pd.DataFrame({'timestamp':pd.to_datetime(['2025-06-10 14:01','2025-06-10 14:02','2025-06-10 14:03']), 'Close':[1,.4,.2],'Low':[.8,.3,.1],'High':[1.1,.7,.3],'Volume':[10]*3})
st=_stop_target_ts(b,b.timestamp[0],1.,TradeVariant(0,False,.5))
print('SPX0 stop close known',st+pd.Timedelta(minutes=1),'exit modeled',exit_fill(b,st,DepthPolicy(),session_floor_ts=b.timestamp.iloc[-1],intrinsic_at_floor=0)[:2])
from unittest.mock import patch
with patch.object(config,'POOL','v6'),patch.object(config,'ensure_dirs',lambda:None),patch.object(bm,'assemble') as ass,patch('sys.argv',['builder','--assemble']):
    bm.main()
    print('V6 ASSEMBLE kwargs',ass.call_args.kwargs)
