"""Bounded, full-variant proposal timelines preserving the frozen simulator rules."""
from copy import deepcopy
import pandas as pd

from nn_meta.v7.signals import signal_batches
from nn_meta.v7.storage import identity


def proposal_batches(symbol, bars, variants, *, start, end, sources=None, batch_columns=16):
    from portfolio.simulator import run_backtest
    from utils.runner_utils import sim_kwargs
    from nn_meta.config import SIM_CONFIG
    from vectorbt.portfolio.enums import TradeStatus
    variants = list(variants)
    minutes = {v['signal_minutes'] for v in variants}
    if len(minutes) != 1 or bars.index.tz is None:
        raise ValueError('One declared timeframe and aware bars are required')
    minutes = minutes.pop()
    begin = pd.Timestamp(start, tz='America/New_York')
    stop = pd.Timestamp(end, tz='America/New_York') + pd.DateOffset(days=1)
    price = bars[(bars.index >= begin) & (bars.index < stop)]
    if price.empty:
        raise ValueError('Proposal simulation window has no observations')
    policy = deepcopy(SIM_CONFIG)
    kwargs = sim_kwargs(policy)
    for records, channels in signal_batches(bars, variants, sources=sources, batch_columns=batch_columns):
        chosen = [c.loc[price.index] for c in channels]
        portfolio = run_backtest(price_df=price, entries_series=chosen[0], exits_series=chosen[1],
            short_entries_series=chosen[2], short_exits_series=chosen[3], frequency=f'{minutes}min', **kwargs)
        if portfolio is None or len(portfolio.wrapper.columns) != len(records):
            raise ValueError('Proposal simulator dropped or changed a variant batch')
        prior, output = {}, []
        for trade in portfolio.trades.records.itertuples():
            variant = records[int(trade.col)]
            entry_pos = int(trade.entry_idx)
            decision = price.index[entry_pos] + pd.Timedelta(minutes=minutes)
            closed = trade.status == TradeStatus.Closed
            exit_at = price.index[int(trade.exit_idx)] + pd.Timedelta(minutes=minutes) if closed else pd.NaT
            key = {'symbol': symbol, 'variant_id': variant['variant_id'], 'decision_ns': decision.value,
                   'right': 'C' if int(trade.direction) == 0 else 'P'}
            gap = entry_pos - prior.get(variant['variant_id'], 0)
            prior[variant['variant_id']] = entry_pos
            output.append({'proposal_id': identity({'schema': 'v7-proposal-v1', **key}), **key,
                           'decision_at': decision, 'exit_decision_at': exit_at,
                           'proposal_closed': closed, 'signal_minutes': minutes,
                           'strategy': variant['strategy'], 'params': variant['params'],
                           'bars_since_previous_signal': gap, 'simulator_policy': policy,
                           'censored_at': pd.NaT if closed else price.index[-1] + pd.Timedelta(minutes=minutes)})
        # Empty variants remain present in the returned catalog batch. No
        # profitability, minimum-trade or maximum-event filtering is applied.
        yield records, output
