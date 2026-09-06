"""Regression tests for causal data, rankings and saved scanner configuration."""
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import vectorbt as vbt


def prices(n=200):
    rng = np.random.default_rng(31)
    c = 100 + np.cumsum(rng.normal(size=n))
    return pd.DataFrame({'Close': c, 'Open': c, 'High': c+rng.uniform(0,2,n),
                         'Low': c-rng.uniform(0,2,n), 'Volume': 100.},
                        index=pd.bdate_range('2025-01-01', periods=n))


def test_elliott_signal_prefix_invariance():
    from indicators.elliott_wave import _detect_swings, _compute_fib_signals_batch
    bars = prices()
    def signals(n):
        sh, sl = _detect_swings(bars.High.values[:n], bars.Low.values[:n], 3)
        return _compute_fib_signals_batch(bars.Close.values[:n], sh, sl,
                                          np.array([.5]), np.array([.02]))
    full = signals(len(bars))
    for n in range(12, len(bars)):
        for prefix, whole in zip(signals(n), full):
            np.testing.assert_array_equal(prefix, whole[:n])


def test_sentiment_not_available_before_publication():
    from sentiment.sentiment_analyzer import aggregate_sentiment
    news = pd.DataFrame({'datetime': pd.to_datetime(['2025-01-02 10:04']),
                         'sentiment_score': [.9]})
    s = aggregate_sentiment(news, '5min')
    assert s.index[0] == pd.Timestamp('2025-01-02 10:05')
    assert s.reindex(pd.to_datetime(['2025-01-02 10:00']), method='ffill').isna().all()


def test_ranking_never_reintroduces_ineligible_filler():
    from utils.param_utils import _rank_portfolio
    idx = pd.Index(['valid','bankrupt','one_trade'])
    series = lambda values: pd.Series(values,index=idx)
    portfolio = SimpleNamespace(wrapper=SimpleNamespace(columns=idx),
        sharpe_ratio=lambda:series([1,2,3]), total_return=lambda:series([.1,-1,.2]),
        max_drawdown=lambda:series([-.1,-1,-.1]),
        trades=SimpleNamespace(win_rate=lambda:series([.5,.1,1]),
                               count=lambda:series([5,5,1])))
    rows = _rank_portfolio(portfolio)
    assert [r['param_label'] for r in rows] == ['param=valid']


def test_chunked_metric_winners_match_full_ranking(monkeypatch):
    from utils import chunked_runner as C
    # A wins both local Sharpe and return, but C wins global Sharpe. A must
    # still beat D for global return even though its local label was Sharpe.
    metrics = {'A': (2, 100, 40), 'B': (1, 10, 50),
               'C': (3, 20, 60), 'D': (1, 50, 55)}
    index = pd.date_range('2025-01-01', periods=4)
    entries = pd.DataFrame(True,index=index,columns=list(metrics))
    def simulate(**kw):
        return SimpleNamespace(wrapper=SimpleNamespace(columns=kw['entries_series'].columns))
    def rank(pf, **kw):
        candidates = list(pf.wrapper.columns)
        out, used = [], set()
        for i, label in enumerate(['Best Sharpe','Best Return','Best Win Rate']):
            winner = max(candidates, key=lambda k: metrics[k][i])
            if winner not in used:
                sh, ret, win = metrics[winner]
                out.append(dict(portfolio_col_int_idx=candidates.index(winner),param_label=winner,
                                ranked_by=label,sharpe_ratio=sh,total_return_pct=ret,win_rate_pct=win))
                used.add(winner)
        return out
    monkeypatch.setattr(C, '_compute_chunk_size', lambda _:2)
    monkeypatch.setattr(C.simulator, 'run_backtest', simulate)
    monkeypatch.setattr(C, 'top5_from_portfolio', rank)
    result=C.simulate_and_rank(prices(4),entries,~entries,None,None,'1D',{})
    assert result['error'] is None
    assert next(r for r in result['top5'] if r['ranked_by']=='Best Return')['param_label']=='A'
    assert len({r['param_label'] for r in result['top5']})==len(result['top5'])


def test_combine_preserves_valid_parameter_tuples():
    from signals.signal_combiners import combine_signals_and
    cols = pd.MultiIndex.from_tuples([(2,4),(2,6),(4,6)],names=['fast','slow'])
    a = pd.DataFrame([[True,False,True]],columns=cols)
    b = pd.DataFrame([[True]],columns=pd.Index([14],name='window'))
    ent, ext = combine_signals_and(a,~a,b,~b)
    assert list(ent.columns)==[(2,4,14),(2,6,14),(4,6,14)]
    np.testing.assert_array_equal(ent.values,a.values)


def test_scanner_rsi_macd_match_sweep():
    from scanner.signal_scanner import _rsi, _check_rsi, _check_macd
    close=prices().Close
    expected=vbt.RSI.run(close,window=14).rsi
    pd.testing.assert_series_equal(_rsi(close,14),expected,check_names=False)
    r=_check_rsi(close,dict(rsi_window=14,entry_threshold=45,exit_threshold=65))
    assert (r['signal']=='BUY') == bool(expected.vbt.crossed_above(45).iloc[-1])
    macd=vbt.MACD.run(close,fast_window=12,slow_window=26,signal_window=9)
    r=_check_macd(close,dict(fast_window=12,slow_window=26,signal_window=9))
    assert r['macd']==round(macd.macd.iloc[-1],4)


def test_scanner_requests_current_data_and_rejects_stale(monkeypatch):
    from scanner import signal_scanner as S
    calls=[]
    def load(*args,**kwargs):
        calls.append((args,kwargs))
        return prices()
    monkeypatch.setattr(S,'load_price_data_smart',load)
    r=S.scan_one(dict(strategy='ma',symbol='SPY',interval='15m',params=dict(fast_window=3,slow_window=5)))
    assert 'Stale' in r['error']
    assert pd.Timestamp(calls[0][0][2]).tzinfo is not None
    assert calls[0][1]['force_download']
    assert not calls[0][1]['use_cache']


def test_volume_save_uses_result_metadata_and_complete_schema(tmp_path,monkeypatch):
    import main
    from utils.param_utils import _format_col_label
    monkeypatch.chdir(tmp_path)
    (tmp_path/'scanner').mkdir()
    cols=pd.MultiIndex.from_tuples([(20,2.,10)],names=['volume_window','volume_multiplier','exit_ma_window'])
    row=dict(symbol='SPY',strategy='Volume Breakout',interval='15m',param_label=_format_col_label(cols[0],cols))
    message,_,color=main.save_to_scanner(1,[0],[row],[{'store_idx':0}], 'MA Crossover','1D')
    assert color=='success',message
    saved=json.loads((tmp_path/'scanner/saved_scans.json').read_text())[0]
    assert saved['strategy']=='volume' and saved['interval']=='15m'
    assert saved['params']==dict(volume_window=20,volume_multiplier=2.,exit_ma_window=10)
    row['param_label']='exit_ma=10'
    assert main.save_to_scanner(1,[0],[row],[{'store_idx':0}],'Volume Breakout','15m')[2]=='danger'


def test_neural_labels_purged_and_unresolved_tail_missing(monkeypatch):
    from models import data_preprocessing as P
    bars=prices(100)
    monkeypatch.setattr(P,'create_features',lambda df,market_df=None:df[['Close']])
    for mode in ['classification','triple_barrier','regression']:
        _,_,train,test,_,_=P.prepare_nn_data(bars,dict(TRAIN_TEST_SPLIT=.8,RETURN_THRESHOLD=.01),5,mode=mode,use_sequences=False)
        assert bars.index.get_loc(train.index[-1])+5 < bars.index.get_loc(test.index[0])
        assert test.index[-1] <= bars.index[-6]
    assert P.create_labels(bars,5,.01).tail(5).isna().all()
    assert P.create_triple_barrier_labels(bars,5,.01,.5).tail(5).isna().all()


def test_cleaner_drops_unobserved_leading_bar():
    from data.data_cleaner import clean_ohlcv_data
    raw=prices(3);raw.iloc[0]=np.nan
    out=clean_ohlcv_data(raw)
    assert out.index[0]==raw.index[1]
    raw.iloc[:]=np.nan
    assert clean_ohlcv_data(raw) is None


def test_old_freeze_refused_and_first_loss_drawdown(tmp_path,monkeypatch):
    from nn_meta import baseline as B
    spec=tmp_path/'spec.json';spec.write_text(json.dumps({'symbols':{},'config_hash':B._config_hash()}))
    monkeypatch.setattr(B.config,'BASELINE_SPEC_JSON',spec)
    with pytest.raises(ValueError,match='re-freeze'):
        B.load_spec()
    assert B.equity_metrics([-.5], f=1)['max_drawdown']==.5


def test_walkforward_uses_history_but_trades_only_oos(monkeypatch):
    from backtests import run_walkforward as W
    bars=prices(200)
    monkeypatch.setattr(W.data_loader,'load_price_data_smart',lambda *a:bars)
    generated=[];simulated=[]
    def generate(strategy,frame,*args):
        generated.append(frame.index)
        signal=(frame.Close.rolling(120).mean().notna()).to_frame('chosen')
        return signal,~signal,None,None
    monkeypatch.setattr(W,'_generate_signals',generate)
    monkeypatch.setattr(W,'simulate_and_rank',lambda **kw:dict(error=None,top5=[dict(portfolio_col_int_idx=0,param_label='chosen')],portfolio=SimpleNamespace(wrapper=SimpleNamespace(columns=['chosen']))))
    def sim(**kw):
        simulated.append(kw['entries_series'])
        return None
    monkeypatch.setattr(W.simulator,'run_backtest',sim)
    W.run('SPY','2025-01-01','2026-01-01','1D',{}, {}, n_folds=1,min_train_pct=.75)
    assert len(generated[-1])==200
    assert simulated[0].index.equals(bars.index[150:])
    assert simulated[0].iloc[0].all()


def test_freeze_resume_refuses_changed_settings(tmp_path, monkeypatch):
    from nn_meta import baseline as B
    from nn_meta.feature_contract import CONTRACT_VERSION
    monkeypatch.setattr(B.config, 'ensure_dirs', lambda:None)
    monkeypatch.setattr(B, 'get_provider', lambda:None)
    dest=tmp_path/'freeze.json'
    dest.write_text(json.dumps(dict(feature_contract_version=CONTRACT_VERSION,
                                    config_hash='outdated',symbols={},skipped=[])))
    with pytest.raises(ValueError,match='settings changed'):
        B.freeze_all(['SPY'],out_path=dest)
    assert json.loads(dest.read_text())['config_hash']=='outdated'


def test_merge_refuses_unversioned_shard(tmp_path):
    from nn_meta import baseline as B
    source=tmp_path/'old.json'
    source.write_text(json.dumps({'symbols':{},'config_hash':B._config_hash()}))
    with pytest.raises(ValueError,match='re-freeze'):
        B.merge_specs([source], tmp_path/'combined.json')
    assert not (tmp_path/'combined.json').exists()


def test_timestamp_bounded_live_fetch_does_not_accumulate_cache_files(tmp_path, monkeypatch):
    from data import vbt_data_loader as L
    monkeypatch.setenv('ALPACA_API_KEY','test-key')
    monkeypatch.setenv('ALPACA_API_SECRET','test-secret')
    monkeypatch.setattr(L,'_download_vbt_alpaca',lambda *args:prices(3))
    cache=tmp_path/'live-cache'
    result=L.load_price_data_smart('SPY','2025-01-01','2025-01-02T15:31:00Z','15m',
                                  cache_dir=str(cache),force_download=True,use_cache=False)
    assert result is not None and not cache.exists()
