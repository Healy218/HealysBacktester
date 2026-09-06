import pandas as pd
from nn_meta.v4_accounting import CostScenario, mark_to_market_portfolio
from nn_options_signal.backtest import run_backtest
z=CostScenario(fee=0,slippage=0)
def book(first=-.9, terminal=0, declared=0):
 t=pd.DataFrame({'trade_id':['a'],'symbol':['A'],'signal_ts':pd.to_datetime(['2025-01-02 09:30']),'fill_entry_ts':pd.to_datetime(['2025-01-02 09:45']),'fill_exit_ts':pd.to_datetime(['2025-01-02 10:00']),'gross_return':[declared]})
 m=pd.DataFrame({'trade_id':['a','a'],'mark_ts':pd.to_datetime(['2025-01-02 09:45','2025-01-02 10:00']),'gross_return':[first,terminal]})
 return mark_to_market_portfolio(t,m,max_concurrent=1,position_fraction=1,costs=z)[0]
print('entry dip ignored', book())
print('mismatching exit accepted', book(first=0,terminal=10,declared=-1))
t=pd.DataFrame({'trade_id':['a','b'],'symbol':['A','B'],'signal_ts':pd.to_datetime(['2025-01-02 09:30','2025-01-02 09:45']),'fill_entry_ts':pd.to_datetime(['2025-01-02 09:45','2025-01-02 10:00']),'fill_exit_ts':pd.to_datetime(['2025-01-02 10:30','2025-01-02 10:30']),'gross_return':[1,0]})
m=pd.DataFrame({'trade_id':['a','a','a','b','b'],'mark_ts':pd.to_datetime(['2025-01-02 09:45','2025-01-02 10:00','2025-01-02 10:30','2025-01-02 10:00','2025-01-02 10:30']),'gross_return':[0,1,1,0,0]})
print('unfunded cash',mark_to_market_portfolio(t,m,max_concurrent=2,position_fraction=.5,costs=z))
p=pd.DataFrame([{'date':pd.Timestamp('2025-01-02'),'pred':1.,'entry_open':10.,'exit_close_h3':0.,'exit_date_h3':pd.Timestamp('2025-01-08'),'ticker':'a','type':'call','strike':100,'dte':20}])
r=run_backtest(p,'pred',3)
print('daily first loss dd',r['total_return'],r['max_drawdown'])
from nn_meta.mark_stream import marks_from_legs
legs=[{'entry_open':1.,'exit_close':1.,'bar_ts':pd.to_datetime(['2025-01-02 09:45','2025-01-02 10:00']),'bar_close':[1.,1.]},{'entry_open':1.,'exit_close':1.,'bar_ts':pd.to_datetime(['2025-01-02 10:15','2025-01-02 10:30']),'bar_close':[1.,1.]}]
roll=marks_from_legs(legs).assign(trade_id='a')
tr=t.iloc[:1].copy(); tr['gross_return']=0
actual=mark_to_market_portfolio(tr,roll,max_concurrent=1,position_fraction=1,costs=CostScenario(fee=.01,slippage=0))[0]['total_return']
print('two leg flat costs actual/expected',actual,(.99/1.01)**2-1)
missing=p.copy(); missing['ticker']='missing'; missing['pred']=2.; missing['exit_close_h3']=float('nan'); missing['exit_date_h3']=pd.NaT
p['exit_close_h3']=20.
for panel in (pd.concat([missing,p]),pd.concat([missing.assign(exit_close_h3=0.,exit_date_h3=pd.Timestamp('2025-01-08')),p])):
 r=run_backtest(panel,'pred',3); print('future exit changes chosen ticker',r['trades']['ticker'].tolist(),r['total_return'])
from nn_meta.vol_features import session_rv
bars=pd.DataFrame({'Open':[100.,100.],'Close':[100.,101.]},index=pd.to_datetime(['2025-01-02 20:58','2025-01-02 20:59']))
print('vol available_at (last bar close only at21:00)',session_rv(bars)['available_at'].iloc[0])
from nn_meta.calibration import fit_isotonic
for labels in ([1,0,0],[0,1,0]):
    cal=fit_isotonic([.5,.5,.6],labels)
    print('isotonic equal-score label order',labels,cal.predict([.5,.6]))
