"""Action-epoch feature construction in contemporaneous price and tick units.

Every epoch recalculates the prefix in the units available in that epoch and
retains only its own completed observations. Past outputs are never replaced
by a later adjusted chart. Original action evidence remains a separate gate.
"""
from dataclasses import dataclass
import pandas as pd

from nn_meta.session_calendar import SessionCalendar
from nn_meta.v7.bars import aggregate_frame
from nn_meta.v7.causal_prices import CausalPriceHistory, PriceAction
from nn_meta.v7.context import chart_context
from nn_meta.v7.features import source_frames, project, technical
from nn_meta.v7.rows import FeatureRows
from nn_meta.v7.scope import require_research_window


@dataclass
class FeatureEpoch:
    start: pd.Timestamp
    end: pd.Timestamp
    security_id: str
    bars: pd.DataFrame
    observed: pd.DatetimeIndex
    context: dict
    technical: pd.DataFrame
    tv: pd.DataFrame
    sources: dict
    action_ids: tuple

    def rows(self, *, daily, symbol, sectors):
        return FeatureRows(self.bars, self.context, self.technical, self.tv, daily,
                           symbol=symbol, security_id=self.security_id, sector=sectors)


class CausalFeatures:
    """One security and a cold-start raw-minute history, with one epoch in memory."""
    def __init__(self, raw, actions, calendar, *, security_id, minutes, start, end, minimum_tick=.01):
        require_research_window(start, end)
        if minutes not in (1, 5, 15, 30):
            raise ValueError('Registered signal timeframe required')
        self.begin = pd.Timestamp(start, tz='America/New_York').tz_convert('UTC')
        self.stop = (pd.Timestamp(end, tz='America/New_York')+pd.DateOffset(days=1)).tz_convert('UTC')
        self.calendar, self.minutes = calendar, minutes
        self.minimum_tick = minimum_tick
        selected = raw.loc[(raw.index >= self.begin) & (raw.index < self.stop)].copy()
        actions = list(actions)
        if not all(isinstance(action, PriceAction) for action in actions):
            raise ValueError('Explicit typed action evidence required')
        self.history = CausalPriceHistory(selected, [a for a in actions if self.begin <= a.effective_at < self.stop],
                                           security_id=security_id)
        if ((selected.index.asi8 % 60_000_000_000 != 0).any()
                or not pd.DatetimeIndex(selected.available_at).equals(selected.index+pd.Timedelta(minutes=1))):
            raise ValueError('Exact completed raw minute observations required')
        sessions = SessionCalendar(calendar)
        for action in self.history.actions:
            if not self.begin <= action.effective_at < self.stop:
                continue
            day = action.effective_at.tz_convert('America/New_York').date().isoformat()
            bounds = sessions.bounds(day)
            if bounds is None or bounds[0].tz_localize('UTC') != action.effective_at:
                raise ValueError('Price actions must use a verified regular-session effective open')

    def _views(self):
        for start, end in self.history.epochs(start=self.begin, end=self.stop):
            as_of = end-pd.Timedelta(nanoseconds=1)
            minute = self.history.view(as_of)
            if minute.empty:
                continue
            bars = aggregate_frame(minute, self.calendar, self.minutes)
            # A partially observed final bucket is not available until its close.
            bars = bars.loc[bars.available_at.le(as_of)]
            observed = bars.index[(bars.available_at >= start) & (bars.available_at < end)]
            if observed.empty:
                continue
            yield start, end, minute, bars, observed

    def epochs(self):
        for start, end, minute, bars, observed in self._views():
            context = chart_context(bars, minute, self.calendar, self.minutes)
            sources = source_frames(bars, context, minimum_tick=self.minimum_tick, observation_index=observed)
            tv = project(bars, sources, context).loc[observed]
            tv.attrs.update(price_basis='v7-causal-asof-chart-v1', security_id=self.history.security_id,
                            action_ids=list(minute.attrs['action_ids']), minimum_tick=self.minimum_tick)
            yield FeatureEpoch(start, end, self.history.security_id, bars, observed, context,
                               technical(bars, context), tv, sources, tuple(minute.attrs['action_ids']))

    def proposal_basis(self):
        """Economic continuity for stop state; execution still requires raw prices."""
        return aggregate_frame(self.history.proposal_basis(), self.calendar, self.minutes)

    def signal_batches(self, variants, *, batch_columns=16, working_bytes=128*1024**2):
        """Correct bounded baseline; epoch calculations may be cached by a disk builder.

        Each batch retains only four boolean channels for its variants. This
        intentionally makes no full-history throughput/resource admission claim.
        """
        import numpy as np
        from nn_meta.v7.signals import signal_batches
        from nn_meta.tradingview_proposals import SOURCE_METADATA
        variants = list(variants)
        if not variants or any(v['signal_minutes'] != self.minutes for v in variants):
            raise ValueError('Variants must match the causal chart timeframe')
        index = self.proposal_basis().index
        width = min(batch_columns, working_bytes//max(1, len(index)*40))
        if width < 1:
            raise ValueError('Working budget cannot hold one full-history signal column')
        for offset in range(0, len(variants), width):
            chosen = variants[offset:offset+width]
            ids = [v['variant_id'] for v in chosen]
            channels = [pd.DataFrame(False, index=index, columns=ids) for _ in range(4)]
            seen = np.zeros(len(index), dtype=bool)
            aliases = {SOURCE_METADATA[v['strategy']]['alias'] for v in chosen if v['strategy'] in SOURCE_METADATA}
            for _, _, minute, bars, observed in self._views():
                sources = None
                if aliases:
                    context = chart_context(bars, minute, self.calendar, self.minutes)
                    sources = source_frames(bars, context, minimum_tick=self.minimum_tick, aliases=aliases)
                positions = index.get_indexer(observed)
                if (positions < 0).any() or seen[positions].any():
                    raise ValueError('Duplicate or foreign causal epoch observations')
                seen[positions] = True
                covered = []
                for records, values in signal_batches(bars, chosen, sources=sources,
                                      batch_columns=width, working_bytes=working_bytes):
                    columns = [v['variant_id'] for v in records]
                    covered.extend(columns)
                    for destination, source in zip(channels, values):
                        destination.loc[observed, columns] = source.loc[observed, columns]
                if sorted(covered) != sorted(ids):
                    raise ValueError('Causal signal generation omitted a registered variant')
            if not seen.all():
                raise ValueError('Causal signal epochs do not cover all completed chart bars')
            yield chosen, tuple(channels)
