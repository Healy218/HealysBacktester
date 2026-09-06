import sys
sys.path.insert(0,'.')
import numpy as np,pandas as pd
from types import SimpleNamespace
from indicators.elliott_wave import _detect_swings,_compute_fib_signals_batch
rng=np.random.default_rng(31)
c=100+np.cumsum(rng.normal(size=200));h=c+rng.uniform(0,2,200);l=c-rng.uniform(0,2,200)
def sig(n):
 sh,sl=_detect_swings(h[:n],l[:n],3)
 return _compute_fib_signals_batch(c[:n],sh,sl,np.array([.5]),np.array([.02]))
full=sig(200)
for n in range(12,199):
 small=sig(n)
 if any(not np.array_equal(a,b[:n]) for a,b in zip(small,full)):
  print('ELLIOTT prefix',n,'differs on already elapsed signal bars',[(i,np.flatnonzero(a[:,0]!=b[:n,0]).tolist()) for i,(a,b) in enumerate(zip(small,full))]);break
from sentiment.sentiment_analyzer import aggregate_sentiment
s=aggregate_sentiment(pd.DataFrame({'datetime':pd.to_datetime(['2026-09-04 10:04']), 'sentiment_score':[.9]}),'5min');print('NEWS timestamp',s.index[0])
from signals.signal_combiners import _get_combined_index
x=pd.DataFrame([[True]*3],columns=pd.MultiIndex.from_tuples([(2,4),(2,6),(4,6)],names=['fast','slow'])); y=pd.DataFrame([[True]],columns=pd.Index([14],name='rsi'))
print('COMBINER expected columns',3,'actual',len(_get_combined_index(x,y)))
from utils.param_utils import _rank_portfolio,_shorten_level_name
idx=pd.Index(['valid','bankrupt','one_trade']); series=lambda a:pd.Series(a,index=idx)
p=SimpleNamespace(wrapper=SimpleNamespace(columns=idx),sharpe_ratio=lambda:series([1,2,3]),total_return=lambda:series([.1,-1,.2]),max_drawdown=lambda:series([-.1,-1,-.1]),trades=SimpleNamespace(win_rate=lambda:series([.5,.1,1]),count=lambda:series([5,5,1]),returns=SimpleNamespace(max=lambda:series([.1,.1,.1]))))
print('RANKED',[(r['param_label'],r['total_trades']) for r in _rank_portfolio(p)])
print('VOLUME label keys',[_shorten_level_name(n) for n in ['volume_window','volume_multiplier','exit_ma_window']])
from scanner.signal_scanner import _rsi
import vectorbt as vbt
price=pd.Series(c)
print('RSI scanner',_rsi(price,14).iloc[-1],'backtest',vbt.RSI.run(price,window=14).rsi.iloc[-1])
from data.data_cleaner import clean_ohlcv_data
raw=pd.DataFrame({k:[np.nan,42.] for k in ['Open','High','Low','Close','Volume']},index=pd.to_datetime(['2026-09-03','2026-09-04']))
print('CLEANER first close',clean_ohlcv_data(raw).Close.iloc[0])
