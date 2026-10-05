"""ETFE catalog/event diagnostics, independent of old feature arrays or metadata."""
from dataclasses import dataclass
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from nn_meta.etfe.purchase_policy_v2 import dte_fraction

ROOT = Path(__file__).resolve().parents[2]
SETUPS = ('BRT','DIV','EMA','ORB','SWEEP','VWAP')
SECTORS = ('idx_etf','sec_etf','tech','semis','fin','crypto','defensive','cyclical','spec')


def names():
    fields = json.loads((ROOT/'docs/specs/ETFE_FEATURE_MAP_20261003.json').read_text())['fields']
    return [f['name'] for f in fields[25:58]+fields[164:]]


def static_names():
    return [n for n in names() if n.startswith(('strat_','timeframe_','param_'))]


def catalog_features(records):
    if not records or len({r['variant_id'] for r in records}) != len(records):
        raise ValueError('Unique nonempty ETFE catalog required')
    fields = static_names(); rows=[]; reasons=[]
    families = {n.removeprefix('strat_') for n in fields if n.startswith('strat_')}
    for r in records:
        if r['expert'] != 'etfe' or r['strategy'] not in families or r['signal_minutes'] not in (1,5,15):
            raise ValueError('Unknown ETFE identity')
        params = r['params']; identity = params.get('setup_identity')
        if (r['strategy']=='tv_setup') != (identity in SETUPS): raise ValueError('Setup identity mismatch')
        value={}; reason={}
        for n in fields:
            if n.startswith('strat_'): v=float(r['strategy']==n[6:])
            elif n.startswith('timeframe_'): v=float(r['signal_minutes']==int(n[10:]))
            elif n.removeprefix('param_setup_') in SETUPS:
                v=float(identity==n.removeprefix('param_setup_')) if identity is not None else np.nan
            else:
                key=n.removeprefix('param_'); v=params.get(key, np.nan)
                if isinstance(v, (bool,str)) or (key in params and not math.isfinite(v)):
                    raise ValueError('Finite numeric catalog parameter required')
                v=float(v)
            value[n]=v; reason[n]='structural_absence' if pd.isna(v) else 'catalog_identity'
        rows.append(value); reasons.append(reason)
    index=pd.Index([r['variant_id'] for r in records],name='variant_id')
    return pd.DataFrame(rows,index=index,dtype='float64'),pd.DataFrame(reasons,index=index)


def signal_history(bars, records, batches, *, observation_start, position_sink=None):
    """Count chart positions in the full prefix; target replicas never reset age."""
    if not bars.valid.all(): raise ValueError('Signal age cannot bridge incomplete source bins')
    expected={r['variant_id']:r for r in records}; seen=set(); rows=[]
    windows={10,30}
    for r in records:
        if r['strategy']=='ma': windows.update((r['params']['fast_window'],r['params']['slow_window']))
    means={int(w):bars.Close.rolling(int(w)).mean().to_numpy() for w in windows}
    closes=bars.Close.to_numpy(); ns=pd.DatetimeIndex(bars.bar_end).as_unit('ns').asi8
    for batch,channels in batches:
        for r in batch:
            vid=r['variant_id']
            if vid in seen or expected.get(vid)!=r: raise ValueError('Signal/catalog identity drift')
            seen.add(vid)
            fast=r['params']['fast_window'] if r['strategy']=='ma' else 10
            slow=r['params']['slow_window'] if r['strategy']=='ma' else 30
            for channel,direction in ((0,'long'),(2,'short')):
                series=channels[channel][vid]
                if not series.index.equals(bars.index) or series.isna().any() or series.dtype!=bool:
                    raise ValueError('Boolean aligned signal required')
                positions=np.flatnonzero(series.to_numpy())
                if position_sink is not None:
                    position_sink.append(dict(variant_id=vid,direction=direction,positions=positions.tolist()))
                previous=None
                for pos in positions:
                    if ns[pos]>=pd.Timestamp(observation_start).value:
                        rows.append(dict(variant_id=vid,strategy=r['strategy'],direction=direction,
                            signal_at_ns=int(ns[pos]),bar_position=int(pos),
                            previous_position=previous if previous is not None else -1,
                            previous_signal_at_ns=int(ns[previous]) if previous is not None else -1,
                            dir_short=float(direction=='short'),
                            bars_since_signal=math.log1p(pos-previous) if previous is not None else np.nan,
                            ma_gap=(means[fast][pos]-means[slow][pos])/closes[pos],
                            px_vs_fast=closes[pos]/means[fast][pos]-1))
                    previous=int(pos)
    if seen!=set(expected): raise ValueError('Incomplete variant replay')
    return pd.DataFrame(rows).sort_values(['variant_id','direction','signal_at_ns']).reset_index(drop=True)


def aware(value):
    t=pd.Timestamp(value)
    if pd.isna(t) or t.tzinfo is None: raise ValueError('Aware nonmissing evidence clock required')
    return t


@dataclass(frozen=True)
class IdentityEvidence:
    key: str
    effective_at: pd.Timestamp
    ends_at: pd.Timestamp
    available_at: pd.Timestamp
    sha256: str
    values: dict

    def __post_init__(self):
        for n in ('effective_at','ends_at','available_at'): object.__setattr__(self,n,aware(getattr(self,n)))
        if self.effective_at>=self.ends_at or len(self.sha256)!=64 or any(c not in '0123456789abcdef' for c in self.sha256):
            raise ValueError('Valid evidence interval and SHA256 required')


def select_evidence(evidence,key,at):
    at=aware(at)
    matches=[e for e in evidence if e.key==key and e.effective_at<=at<e.ends_at and e.available_at<=at]
    if len(matches)>1: raise ValueError('Ambiguous dated identity')
    return matches[0] if matches else None


def contract_features(symbol,at,spot,*,direction,evidence=()):
    at=aware(at)
    if direction not in ('long','short') or not math.isfinite(spot) or spot<=0: raise ValueError('Invalid event')
    proof=select_evidence(evidence,symbol,at) if symbol is not None else None
    if proof is None:
        return dict(dte_frac=np.nan,moneyness=np.nan), 'dated_selected_contract_unresolved'
    v=proof.values
    if v['right'] != ('call' if direction=='long' else 'put'): raise ValueError('Direction/right mismatch')
    if not math.isfinite(v['strike']) or v['strike']<=0: raise ValueError('Positive dated strike required')
    return dict(dte_frac=dte_fraction(v['expiration_date'],at),moneyness=math.log(v['strike']/spot)), 'dated_identity'


def sector_features(ticker,at,*,evidence=()):
    proof=select_evidence(evidence,ticker,at)
    if proof is None:return {f'sec_{n}':np.nan for n in SECTORS},'dated_sector_unresolved'
    sector=proof.values['sector']
    if sector not in SECTORS: raise ValueError('Unknown sector')
    return {f'sec_{n}':float(sector==n) for n in SECTORS},'dated_identity'
