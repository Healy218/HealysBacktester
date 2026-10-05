"""Fresh ETFE TV diagnostics; registry parameters, explicit causal prerequisites.

Only numerical kernels are reused. No prior pool, cache, schema or model is read.
"""
from copy import deepcopy
import importlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from nn_meta.etfe.causal_inputs import PRICE_COLUMNS, minute_context
from v3.pine_compat import atr
from v3._tv_trend_support import pine_ohlc

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / 'docs/specs/ETFE_FEATURE_MAP_20261003.json'
PHASE = {'idle': 0, 'accum': 1, 'sweepPending': 2, 'manip': 3, 'dist': 4}


def bindings():
    """Compile the frozen registry without eval or a legacy feature registry."""
    result = []
    for spec in json.loads(REGISTRY.read_text())['fields']:
        if not spec['name'].startswith('tv_'):
            continue
        source, field = spec['source'].split('; source-bound native field ')
        alias = source.removeprefix('tv_scopes.')
        formula = spec['formula']; term = f'{alias}.{field}'
        allowed = {f'float({term})': 'value', f'({term}-Close)/Wilder_ATR14': 'price',
                   f'{term}/Wilder_ATR14': 'range', f'{term}/100': 'percent',
                   'map(amd.phase,idle=0,accum=1,sweepPending=2,manip=3,dist=4)': 'phase'}
        if formula not in allowed:
            raise ValueError(f'Unrecognized frozen formula: {formula}')
        gates = []
        def gate(column, operation='finite'):
            gates.append([column, operation])
        if alias == 'gaussian' and field != 'smoothed_efficiency':
            gate('trend_width')
        if alias == 'fibonacci' and field in ('direction', 'bull_signal', 'bear_signal', 'trend_flip'):
            gate('upper_band')
        if alias == 'uptrick' and field != 'regime':
            gate('regime'); gate('dynamic_gate')
        if alias == 'structure' and field in ('market_direction', 'bull_signal', 'bear_signal'):
            for col in ('high_0', 'high_1', 'low_0', 'low_1'): gate(col)
        if alias == 'sr':
            if field in ('inside_channel', 'bull_signal', 'bear_signal'): gate('pivot_count', 'positive')
            if field == 'channel_1_strength': gate('channel_1_top')
        if alias == 'probability' and field != 'rsi':
            gate('signal'); gate('atr')
            if field.startswith('raw_'): gate('previous_signal')
            if field.endswith('reference_win_pct'): gate(field.split('_')[0] + '_resolved', 'positive')
        if alias == 'ict' and '_break_' in field:
            session, side = field.split('_break_'); gate(f'{session}_confirmed_{side}')
        if alias == 'order_blocks' and ('count' in field or 'retest' in field):
            gate('atr'); gate('volume_sma')
        if alias == 'amd' and field in ('phase', 'long_entry', 'short_entry', 'all_closed'):
            gate('compression_rank')
        if alias == 'setup' and '_raw_' in field:
            gate('atr', 'positive'); identity = field.split('_')[0]
            if identity in ('VWAP', 'EMA', 'SWEEP'): gate('volume_sma')
            if identity == 'VWAP': gate('vwap'); gate('previous_vwap')
            if identity == 'EMA':
                for col in ('ema9', 'ema21', 'ema50'): gate(col)
            if identity == 'DIV': gate('rsi'); gate('pivot_history_ready', 'true')
            if identity == 'BRT': gate('pivot_history_ready', 'true')
            if identity == 'ORB': gate('or_done', 'true')
        if alias == 'liquidity':
            if field == 'profile_ready': gate('bin_step', 'positive')
            # Sweep can invalidate the current level; test the prior anchor.
            if field == 'top_sweep': gate('previous_top')
            if field == 'bottom_sweep': gate('previous_bottom')
        if alias == 'htf':
            if field == 'delta_pct': gate('directional_volume', 'positive')
            if field == 'profile_ready': gate('regression_end')
            if field == 'completed_profile_ready': gate('completed_regression_end')
        if alias == 'footprint' and field in ('chart_poc_fresh', 'window_bars'):
            gate('total_volume', 'positive')
        if spec['valid_when']: gate(spec['valid_when'], 'true')
        result.append(dict(name=spec['name'], source=alias, field=field,
                           transform=allowed[formula], gates=gates))
    if len(result) != 96 or len({r['name'] for r in result}) != 96:
        raise ValueError('Expected exactly 96 registered TV fields')
    return result


def htf_flags(bars, minutes):
    """Actual session opens; immutable full-calendar ordinal for two-day groups."""
    if minutes not in (1, 5, 15): raise ValueError('ETFE timeframe')
    if minutes == 15:
        keys = bars.session_ordinal // 2; period = '2D'
    else:
        duration = 240 if minutes == 1 else 720; period = str(duration)
        offset = ((bars.index - pd.DatetimeIndex(bars.session_open)).total_seconds() // (duration * 60)).astype(int)
        keys = pd.Series(list(zip(bars.session_ordinal, offset)), index=bars.index)
    flags = keys.ne(keys.shift()); flags.attrs['htf_period'] = period
    return flags


def native_frames(bars, raw, minutes, observations=None):
    if os.environ.get('NN_META_V6_ACCELERATE') == '1':
        raise ValueError('ETFE reference study requires unaccelerated numerical kernels')
    if bars.empty or not bars.valid.all(): raise ValueError('Complete nonempty prefix required')
    if not bars.index.is_unique or not bars.index.is_monotonic_increasing or bars.index.tz is None:
        raise ValueError('Ordered unique aware grid required')
    if not pd.DatetimeIndex(bars.bar_end).equals(bars.index + pd.Timedelta(minutes=minutes)):
        raise ValueError('Close clock differs from timeframe')
    if bars.available_at.isna().any() or (bars.available_at > bars.bar_end).any():
        raise ValueError('Stock publication exceeds decision close')
    observations = bars.index if observations is None else observations
    positions = bars.index.get_indexer(observations)
    if (positions < 0).any() or not observations.is_unique or not observations.is_monotonic_increasing:
        raise ValueError('Unknown/duplicate/unordered observation')
    context = minute_context(bars, raw); frames = {}
    for scope in json.loads(REGISTRY.read_text())['tv_scopes']:
        alias = scope['scope']; module, function = scope['calculator'].rsplit('.', 1)
        calc = getattr(importlib.import_module(module), function)
        kwargs = deepcopy(scope['parameters'])
        if alias == 'setup':
            from nn_meta.v7.setup import setup_scanner
            calc = setup_scanner
            kwargs.update(opening_observations=context['opening'], vwap_observations=context['vwap'])
        if alias == 'amd':
            from v3.tv_amd_po3 import AmdConfig
            kwargs['config'] = AmdConfig(**kwargs['config'])
        if 'bar_minutes' in kwargs: kwargs['bar_minutes'] = minutes
        if 'as_of' in kwargs: kwargs['as_of'] = bars.bar_end.iloc[-1]
        if alias == 'htf': kwargs.update(chart_period=str(minutes), htf_change=htf_flags(bars, minutes))
        if alias in ('htf', 'footprint'): kwargs['observation_positions'] = positions.tolist()
        frame = calc(bars[PRICE_COLUMNS], **kwargs)
        if not frame.index.equals(observations if alias in ('htf', 'footprint') else bars.index):
            raise ValueError(f'{alias}: changed observation index')
        if 'available_at' in frame and not pd.DatetimeIndex(frame.available_at).equals(frame.index + pd.Timedelta(minutes=minutes)):
            raise ValueError(f'{alias}: availability drift')
        if alias == 'probability':
            frame['previous_signal'] = frame.signal.shift()
            for side in ('long', 'short'): frame[side + '_resolved'] = frame[f'total_{side}_wins'] + frame[f'total_{side}_losses']
        if alias == 'setup':
            frame['previous_vwap'] = frame.vwap.shift()
            frame['pivot_history_ready'] = np.arange(len(frame)) >= 2 * kwargs['pivot_length']
        if alias == 'liquidity':
            frame['previous_top'] = frame.liquidity_top.shift(); frame['previous_bottom'] = frame.liquidity_bottom.shift()
        frames[alias] = frame.loc[observations].copy()
    return frames


def prerequisites(native, gates):
    ready = pd.Series(True, index=native.index)
    for column, op in gates:
        value = native[column]
        if op == 'finite': ready &= np.isfinite(value)
        elif op == 'positive': ready &= np.isfinite(value) & value.gt(0)
        elif op == 'true': ready &= value.eq(True)
        else: raise ValueError('Unknown readiness predicate')
    return ready


def project(bars, frames):
    index = next(iter(frames.values())).index
    scale = atr(pine_ohlc(bars[PRICE_COLUMNS]), 14).loc[index]
    values = {}; reasons = {}
    for b in bindings():
        frame = frames[b['source']]; raw = frame[b['field']]
        value = raw.map(PHASE).astype(float) if b['transform'] == 'phase' else raw.astype(float)
        why = pd.Series('observed_diagnostic', index=index)
        why.loc[~np.isfinite(value)] = 'native_unavailable'
        ready = prerequisites(frame, b['gates'])
        why.loc[~ready] = 'native_prerequisite_unavailable'
        value = value.where(ready)
        if b['transform'] in ('price', 'range'):
            valid_scale = np.isfinite(scale) & scale.gt(0)
            why.loc[~valid_scale] = 'atr14_unavailable_or_zero'
            numerator = value - bars.Close.loc[index] if b['transform'] == 'price' else value
            value = numerator / scale.where(valid_scale)
        elif b['transform'] == 'percent': value = value / 100.
        if np.isinf(value).any(): raise ValueError('Infinite TV projection')
        if not value.isna().equals(why.ne('observed_diagnostic')): raise ValueError('Reason/value mismatch')
        values[b['name']] = value; reasons[b['name']] = why
    return pd.DataFrame(values), pd.DataFrame(reasons)


def compute(bars, raw, minutes, observations=None):
    """Missing bins taint every later recurrence; never drop/restart a gap."""
    observations = bars.index if observations is None else observations
    if (bars.index.get_indexer(observations) < 0).any() or not observations.is_unique or not observations.is_monotonic_increasing:
        raise ValueError('Unknown/duplicate/unordered observation')
    names = [b['name'] for b in bindings()]
    values = pd.DataFrame(np.nan, index=observations, columns=names)
    reasons = pd.DataFrame('incomplete_source_prefix', index=observations, columns=names)
    good = bars.valid.astype(bool).cummin(); prefix = bars.loc[good]
    selected = observations[observations.isin(prefix.index)]
    frames = {}
    if len(selected):
        frames = native_frames(prefix, raw, minutes, selected)
        v, r = project(prefix, frames); values.loc[selected] = v; reasons.loc[selected] = r
    return values, reasons, frames
