"""As-of chart prices from raw observations and explicitly available actions.

Each action's factor converts *earlier* prices to the units after that action.
No current-share cumulative vendor factor or rounded adjusted price is used.
Actions are reconstruction inputs; their source/publication evidence must be
validated separately before full-universe admission.
"""
from dataclasses import dataclass
import math

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PriceAction:
    event_id: str
    effective_at: pd.Timestamp
    available_at: pd.Timestamp
    price_factor: float
    volume_factor: float
    source_identity: str

    def __post_init__(self):
        if not self.event_id or not self.source_identity:
            raise ValueError('Action and source identities required')
        for name in ('effective_at', 'available_at'):
            value = pd.Timestamp(getattr(self, name))
            if pd.isna(value) or value.tzinfo is None:
                raise ValueError('Timezone-aware action times required')
            object.__setattr__(self, name, value.tz_convert('UTC'))
        if self.available_at > self.effective_at:
            raise ValueError('Action factor was not available at its effective time')
        if any(isinstance(v, bool) or not math.isfinite(v) or v <= 0
               for v in (self.price_factor, self.volume_factor)):
            raise ValueError('Positive finite action factors required')


def split_action(*, old_shares, new_shares, **evidence):
    if any(isinstance(v, bool) or not math.isfinite(v) or v <= 0 for v in (old_shares, new_shares)):
        raise ValueError('Positive finite split share counts required')
    return PriceAction(price_factor=old_shares / new_shares,
                       volume_factor=new_shares / old_shares, **evidence)


def cash_distribution_action(*, cash_per_share, prior_raw_close, prior_close_at, **evidence):
    """Declared prior-close chart adjustment; not a total-return cash ledger."""
    if (any(isinstance(v, bool) or not math.isfinite(v) for v in (cash_per_share, prior_raw_close))
            or not 0 < cash_per_share < prior_raw_close):
        raise ValueError('Distribution must be positive and below the prior raw close')
    prior_close_at = pd.Timestamp(prior_close_at)
    effective_at = pd.Timestamp(evidence['effective_at'])
    available_at = pd.Timestamp(evidence['available_at'])
    if (prior_close_at.tzinfo is None or pd.isna(prior_close_at)
            or effective_at.tzinfo is None or available_at.tzinfo is None
            or prior_close_at >= effective_at):
        raise ValueError('Observed prior raw close must precede the action')
    evidence['available_at'] = max(available_at, prior_close_at)
    return PriceAction(price_factor=1 - cash_per_share / prior_raw_close,
                       volume_factor=1., **evidence)


class CausalPriceHistory:
    def __init__(self, raw, actions, *, security_id):
        required = ['Open', 'High', 'Low', 'Close', 'Volume']
        if (not security_id or not isinstance(raw.index, pd.DatetimeIndex)
                or raw.index.tz is None or raw.index.hasnans or raw.index.has_duplicates
                or not raw.index.is_monotonic_increasing or not len(raw)
                or not set(required).issubset(raw)):
            raise ValueError('Explicit security and ordered timezone-aware raw OHLCV required')
        values = raw[required].to_numpy(float)
        if (not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any()
                or (raw.High < raw[['Open', 'Low', 'Close']].max(axis=1)).any()
                or (raw.Low > raw[['Open', 'High', 'Close']].min(axis=1)).any()):
            raise ValueError('Invalid raw OHLCV')
        if 'available_at' not in raw:
            raise ValueError('Explicit completed-bar availability required')
        available = pd.DatetimeIndex(raw.available_at)
        if (available.tz is None or available.hasnans or not available.is_monotonic_increasing
                or (available <= raw.index).any()):
            raise ValueError('Invalid completed-bar availability')
        self.raw = raw.copy(deep=True)
        self.security_id = security_id
        actions = list(actions)
        if not all(isinstance(a, PriceAction) for a in actions):
            raise ValueError('Explicit typed action evidence required')
        if len({a.event_id for a in actions}) != len(actions):
            raise ValueError('Duplicate corporate action identity')
        # Same-time actions require a reviewed combined factor. Multiplying
        # independently priced dividends/splits can double-adjust the dividend.
        if len({a.effective_at for a in actions}) != len(actions):
            raise ValueError('Simultaneous actions require one reviewed combined event')
        self.actions = tuple(sorted(actions, key=lambda a: (a.effective_at, a.event_id)))

    def view(self, as_of, *, start=None):
        """Completed raw bars, adjusted only by actions effective by as_of.

        The resulting chart stays in contemporaneous price/tick units at
        as_of. Consumers must retain only the current epoch's outputs when
        combining calculations across action boundaries.
        """
        as_of = pd.Timestamp(as_of)
        if as_of.tzinfo is None or pd.isna(as_of):
            raise ValueError('Timezone-aware as-of clock required')
        selected = self.raw.available_at.le(as_of)
        if start is not None:
            start = pd.Timestamp(start)
            if start.tzinfo is None or start > as_of:
                raise ValueError('Chronological timezone-aware window required')
            selected &= self.raw.index >= start
        result = self.raw.loc[selected].copy()
        price, volume = np.ones(len(result)), np.ones(len(result))
        used = []
        for action in self.actions:
            if action.effective_at > as_of:
                break
            affected = result.index < action.effective_at
            price[affected] *= action.price_factor
            volume[affected] *= action.volume_factor
            if affected.any():
                used.append(action.event_id)
        if not np.isfinite(price).all() or not np.isfinite(volume).all() or (price <= 0).any():
            raise ValueError('Cumulative action factors are unrepresentable')
        result.loc[:, ['Open', 'High', 'Low', 'Close']] = result[['Open', 'High', 'Low', 'Close']].mul(price, axis=0)
        result.loc[:, 'Volume'] = result.Volume.to_numpy() * volume
        result.attrs.update(price_basis='v7-causal-asof-chart-v1', as_of=as_of.isoformat(),
                            security_id=self.security_id, action_ids=used,
                            tick_basis='contemporaneous instrument units', research_ready=False)
        return result

    def proposal_basis(self):
        """Continuous fixed-origin price basis for cross-epoch stop accounting.

        This is not an execution price. Raw contemporaneous spot remains
        mandatory for contract selection, valuation and cash accounting.
        """
        result = self.raw.copy()
        price, volume = np.ones(len(result)), np.ones(len(result))
        for action in self.actions:
            affected = result.index >= action.effective_at
            price[affected] /= action.price_factor
            volume[affected] /= action.volume_factor
        if not np.isfinite(price).all() or not np.isfinite(volume).all():
            raise ValueError('Cumulative action factors are unrepresentable')
        result.loc[:, ['Open', 'High', 'Low', 'Close']] = result[['Open', 'High', 'Low', 'Close']].mul(price, axis=0)
        result.loc[:, 'Volume'] = result.Volume.to_numpy() * volume
        result.attrs.update(price_basis='v7-causal-fixed-origin-chart-v1',
                            security_id=self.security_id, execution_price=False, research_ready=False)
        return result

    def epochs(self, *, start, end):
        """Half-open calculation intervals with one as-of adjustment basis."""
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        if start.tzinfo is None or end.tzinfo is None or not start < end:
            raise ValueError('Timezone-aware positive epoch interval required')
        cuts = [start, *(a.effective_at for a in self.actions if start < a.effective_at < end), end]
        return list(zip(cuts, cuts[1:]))
