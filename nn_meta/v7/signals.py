"""Shared MA calculations and bounded vectorbt signal columns for V7.

The dominant registered MA family is implemented here. Other families must
explicitly register validated adapters; absence never silently drops variants.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class SharedIndicators:
    """One immutable input series per scope; call identities cannot cross symbols/timeframes."""
    def __init__(self, close):
        if not isinstance(close, pd.Series) or close.empty or close.index.has_duplicates or not close.index.is_monotonic_increasing:
            raise ValueError('Expected unique ordered nonempty close series')
        self._close = close.copy(deep=True)
        self._close.to_numpy(copy=False).setflags(write=False)
        self.cache = {}
        self.computations = 0

    @property
    def close(self):
        return self._close.copy(deep=False)

    def moving_averages(self, windows):
        windows = tuple(sorted(set(int(w) for w in windows)))
        if not windows or windows[0] < 1:
            raise ValueError('Positive windows required')
        key = ('sma', windows)
        if key not in self.cache:
            import vectorbt as vbt
            frame = vbt.MA.run(self.close, window=list(windows)).ma
            if isinstance(frame, pd.Series):
                frame = frame.to_frame(name=windows[0])
            values = frame.to_numpy(copy=True)
            values.setflags(write=False)
            frame = pd.DataFrame(values, index=frame.index, columns=list(windows), copy=False)
            self.cache[key] = frame; self.computations += 1
        # Caller receives read-only arrays; numerical cache cannot be changed.
        return self.cache[key].copy(deep=False)


def ma_batches(shared, variants, *, batch_columns=32, working_bytes=128 * 1024**2):
    variants = list(variants)
    if not variants or batch_columns < 1 or working_bytes < 1:
        raise ValueError('Positive batch budget and nonempty variants required')
    if any(r['strategy'] != 'ma' for r in variants):
        raise ValueError('This adapter only admits MA; other families require their own validated adapter')
    if len({r['variant_id'] for r in variants}) != len(variants) or len({r['signal_minutes'] for r in variants}) != 1:
        raise ValueError('Expected distinct variants for one timeframe')
    for r in variants:
        if not 0 < r['params']['fast_window'] < r['params']['slow_window']:
            raise ValueError('Invalid MA windows')
    averages = shared.moving_averages([r['params'][k] for r in variants for k in ('fast_window', 'slow_window')])
    # Two float arrays plus four boolean outputs; also leave budget for copies.
    per_column = max(len(shared.close), 1) * 40
    if working_bytes < per_column:
        raise ValueError('Working budget cannot hold one full-history signal column')
    width = min(batch_columns, working_bytes // per_column)
    for start in range(0, len(variants), width):
        records = variants[start:start + width]
        ids = [r['variant_id'] for r in records]
        fast = averages[[r['params']['fast_window'] for r in records]].copy(); fast.columns = ids
        slow = averages[[r['params']['slow_window'] for r in records]].copy(); slow.columns = ids
        entries = fast.vbt.crossed_above(slow)
        exits = fast.vbt.crossed_below(slow)
        yield records, (entries, exits, exits.copy(), entries.copy())


def signal_batches(bars, variants, *, sources=None, batch_columns=32,
                   working_bytes=128*1024**2):
    """Every registered variant, bounded output columns and shared source frames.

    MA shares all windows; remaining legacy variants retain exact single/sweep
    kernels. TV source frames are computed once, including the shared Setup book.
    No optimization winner or event cap is applied.
    """
    from nn_meta.multitimeframe_catalog import registered_catalog
    from nn_meta.proposals import single_signals
    from nn_meta.tradingview_proposals import SOURCE_METADATA
    variants=list(variants)
    if not variants or len({v['signal_minutes'] for v in variants})!=1:
        raise ValueError('One nonempty timeframe required')
    allowed={v['variant_id']:v for v in registered_catalog(['_validation'])['records']}
    if len({v['variant_id'] for v in variants})!=len(variants) or any(allowed.get(v['variant_id'])!=v for v in variants):
        raise ValueError('Unknown or duplicate catalog variant')
    width=min(batch_columns,working_bytes//max(1,len(bars)*40))
    if width<1:raise ValueError('Working budget cannot hold one signal column')
    ma=[v for v in variants if v['strategy']=='ma']
    if ma:yield from ma_batches(SharedIndicators(bars.Close),ma,batch_columns=width,working_bytes=working_bytes)
    remaining=[v for v in variants if v['strategy']!='ma']
    for first in range(0,len(remaining),width):
        records=remaining[first:first+width];arrays=[[] for _ in range(4)]
        for record in records:
            strategy=record['strategy']
            if strategy in SOURCE_METADATA:
                if sources is None:raise ValueError('Shared full-history TV source frames required')
                alias=SOURCE_METADATA[strategy]['alias'];frame=sources[alias]
                if not frame.index.equals(bars.index):raise ValueError('Signal source must cover all original bars')
                if strategy=='tv_setup':
                    name=record['params']['setup_identity']
                    columns=[name+'_'+s for s in ('long_entry','long_exit','short_entry','short_exit')]
                elif strategy in ('tv_rsi_probability','tv_amd'):
                    columns=['long_entry','long_exit','short_entry','short_exit']
                elif strategy=='tv_fibonacci':
                    columns=['bull_signal','bear_flip','bear_signal','bull_flip']
                else:columns=['bull_signal','bear_signal','bear_signal','bull_signal']
                frames=tuple(frame[[c]] for c in columns)
            else:
                frames=single_signals(strategy,bars,record['params'])
            for out,frame in zip(arrays,frames):
                if frame is None:out.append(np.zeros(len(bars),dtype=bool));continue
                if len(frame.columns)!=1 or not frame.index.equals(bars.index) or frame.isna().any().any():
                    raise ValueError('Signal kernel changed rows or column count')
                if not pd.api.types.is_bool_dtype(frame.iloc[:,0]):raise ValueError('Signals must be boolean')
                out.append(frame.iloc[:,0].to_numpy(copy=True))
        yield records,tuple(pd.DataFrame(np.column_stack(a),index=bars.index,
                                        columns=[r['variant_id'] for r in records]) for a in arrays)
