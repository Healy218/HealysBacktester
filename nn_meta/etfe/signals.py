"""ETFE catalog adapters using only mathematical kernels, never old data/config."""
from copy import deepcopy
import importlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
TV={'tv_gaussian':'gaussian','tv_fibonacci':'fibonacci','tv_uptrick':'uptrick',
    'tv_msb':'structure','tv_sr':'sr','tv_rsi_probability':'probability',
    'tv_amd':'amd','tv_setup':'setup'}


def parameter_values(records,name,*,pad=False):
    values=sorted({r['params'][name] for r in records})
    if pad and len(values)==1:values.append(values[0]+1)
    return np.asarray(values)


def native_family(bars, records, raw):
    """Bind grid values from ETFE's frozen catalog, not old runtime selectors."""
    strategy=records[0]['strategy'];p=lambda name,**kw:parameter_values(records,name,**kw)
    close=bars.Close
    if strategy in TV:
        registry=json.loads((ROOT/'docs/specs/ETFE_FEATURE_MAP_20261003.json').read_text())
        spec=next(x for x in registry['tv_scopes'] if x['scope']==TV[strategy])
        module,name=spec['calculator'].rsplit('.',1)
        calculator=getattr(importlib.import_module(module),name);kwargs=deepcopy(spec['parameters'])
        if strategy=='tv_setup':
            # This pinned module is a pure mathematical ORB/Setup kernel. No V7
            # cache, runtime configuration, schema, reference or model is loaded.
            from nn_meta.v7.setup import setup_scanner
            from nn_meta.etfe.causal_inputs import minute_context
            calculator=setup_scanner;context=minute_context(bars,raw)
            kwargs.update(opening_observations=context['opening'],vwap_observations=context['vwap'])
        if strategy=='tv_amd':
            from v3.tv_amd_po3 import AmdConfig
            kwargs['config']=AmdConfig(**kwargs['config'])
        if 'bar_minutes' in kwargs:kwargs['bar_minutes']=records[0]['signal_minutes']
        if 'as_of' in kwargs:kwargs['as_of']=bars.bar_end.iloc[-1]
        frame=calculator(bars[['Open','High','Low','Close','Volume']],**kwargs)
        if not frame.index.equals(bars.index):raise ValueError('Native signal index changed')
        return frame
    from signals import (rsi_threshold,macd_signals,bbands_breakout,stoch_crossover,
                         volume_breakout,elliott_wave_signals,tv_signals)
    if strategy=='rsi':return rsi_threshold.generate_rsi_signals(close,p('rsi_window',pad=True),p('entry_threshold'),p('exit_threshold'),enable_shorting=True)
    if strategy=='macd':return macd_signals.generate_macd_signals(close,p('macd_fast_window'),p('macd_slow_window'),p('macd_signal_window',pad=True),short_entries=True,short_exits=True)
    if strategy=='bbands':return bbands_breakout.generate_bbands_signals(close,p('bb_window'),p('bb_alpha',pad=True),enable_shorting=True)
    if strategy=='stoch':return stoch_crossover.generate_stoch_signals(bars.High,bars.Low,close,p('stoch_k_window'),p('stoch_d_window',pad=True),oversold_range=p('oversold'),overbought_range=p('overbought'),enable_shorting=True)
    if strategy=='volume':return volume_breakout.generate_volume_signals(bars,volume_window_range=p('volume_window',pad=True),volume_multiplier_range=p('volume_multiplier'),exit_ma_window_range=p('exit_ma_window',pad=True))
    if strategy=='elliott':return elliott_wave_signals.generate_elliott_wave_signals(bars.High,bars.Low,close,p('swing_order'),p('fib_level'),p('fib_tolerance',pad=True),enable_shorting=True)
    funcs={
        'supertrend':(tv_signals.generate_supertrend_signals,['st_window','st_mult']),
        'tv_rating':(tv_signals.generate_tv_rating_signals,['entry_rating','exit_rating']),
        'squeeze':(tv_signals.generate_squeeze_signals,['sq_bb_mult','sq_kc_mult']),
        'keltner':(tv_signals.generate_keltner_signals,['kc_window','kc_mult']),
        'bbw_squeeze':(tv_signals.generate_bbw_squeeze_signals,['bbw_window','bbw_lookback'])}
    if strategy not in funcs:raise ValueError('Unknown ETFE family')
    function,names=funcs[strategy]
    return function(bars,*[p(n) for n in names],enable_shorting=True)


def select_native(frames,record):
    strategy=record['strategy'];params=record['params']
    if strategy in TV:
        if strategy=='tv_setup':columns=[params['setup_identity']+'_'+x for x in ('long_entry','long_exit','short_entry','short_exit')]
        elif strategy in ('tv_amd','tv_rsi_probability'):columns=['long_entry','long_exit','short_entry','short_exit']
        elif strategy=='tv_fibonacci':columns=['bull_signal','bear_flip','bear_signal','bull_flip']
        else:columns=['bull_signal','bear_signal','bear_signal','bull_signal']
        selected=[frames[c] for c in columns]
    else:
        selected=[]
        for frame in frames:
            if frame is None:selected.append(None);continue
            if not isinstance(frame,pd.DataFrame):raise ValueError('Native signal shape changed')
            names=frame.columns.names;found=[]
            for i,key in enumerate(frame.columns):
                key=key if isinstance(key,tuple) else (key,)
                if all(name in params and np.isclose(value,params[name],rtol=0,atol=1e-9) for name,value in zip(names,key)):
                    found.append(i)
            if len(found)!=1:raise ValueError(f'Catalog/native parameter mismatch: {strategy}/{params}')
            selected.append(frame.iloc[:,found[0]])
    for series in selected:
        if series is not None and (series.isna().any() or not pd.api.types.is_bool_dtype(series)):
            raise ValueError('Native signal must be boolean, without coerced missingness')
    return selected


def signal_batches(bars, records, raw, *, width=32):
    if not bars.valid.all():raise ValueError('Signal pilot cannot bridge incomplete bars')
    if width<1 or len({r['signal_minutes'] for r in records})!=1:raise ValueError('One timeframe and positive width required')
    if len({r['variant_id'] for r in records})!=len(records):raise ValueError('Duplicate variant')
    # Frame width is additionally constrained by a 128-MiB temporary-array budget.
    width=min(width,128*2**20//max(1,len(bars)*40))
    if width<1:raise ValueError('One signal column exceeds working budget')
    for family in sorted({r['strategy'] for r in records}):
        chosen=[r for r in records if r['strategy']==family]
        if family=='ma':
            import vectorbt as vbt
            windows=sorted({int(r['params'][name]) for r in chosen for name in ('fast_window','slow_window')})
            ma=vbt.MA.run(bars.Close,window=windows).ma
            averages=pd.DataFrame(ma.to_numpy(),index=bars.index,columns=windows)
            native=None
        else:native=native_family(bars,chosen,raw)
        for offset in range(0,len(chosen),width):
            batch=chosen[offset:offset+width];ids=[r['variant_id'] for r in batch]
            if family=='ma':
                fast=averages[[r['params']['fast_window'] for r in batch]].copy();fast.columns=ids
                slow=averages[[r['params']['slow_window'] for r in batch]].copy();slow.columns=ids
                up=fast.vbt.crossed_above(slow);down=fast.vbt.crossed_below(slow)
                channels=(up,down,down.copy(),up.copy())
            else:
                selected=[select_native(native,r) for r in batch]
                channels=tuple(pd.DataFrame({r['variant_id']:(s[n] if s[n] is not None else False)
                    for r,s in zip(batch,selected)},index=bars.index) for n in range(4))
            yield batch,channels
