"""Full V7 model-facing rows with explicit timeframe and parameter representations."""
from functools import lru_cache
import math
import numpy as np
import pandas as pd

from nn_meta.multitimeframe_catalog import registered_catalog
from nn_meta.tradingview_features import FEATURE_NAMES
from nn_meta.option_tick_dataset import NUMERIC_FEATURES
from nn_meta.v7.sectors import DatedSectors, SECTORS

TECHNICAL = ('ma_gap', 'px_vs_fast', 'rsi14', 'macd_hist', 'bb_z', 'ret_1', 'ret_8', 'ret_26',
             'session_gap', 'gap_abs_z', 'tod', 'dow', 'is_first_hour', 'is_last_hour', 'dow_tod')
DAILY = ('rvol_5', 'rvol_21', 'atm_iv_near', 'atm_iv_far', 'term_slope', 'iv_chg_5', 'pc_ratio',
         'market_iv', 'rv_iv_spread', 'beta_60d')
TRADE = ('dir_short', 'dte_frac', 'moneyness', 'bars_since_signal')
ROW_CONTRACT = {'version': 'v7-selected-contract-rows-v2',
                'dte_frac': 'actual calendar DTE at decision / 9',
                'moneyness': 'log(selected strike / observed raw spot), both rights',
                'spot': 'completed raw minute close, available no more than 60 seconds before decision'}


@lru_cache(maxsize=1)
def schema():
    records = registered_catalog(['_schema'])['records']
    strategies = sorted({r['strategy'] for r in records})
    numeric = sorted({key for r in records for key, value in r['params'].items() if isinstance(value, (int, float))})
    setups = sorted({r['params']['setup_identity'] for r in records if 'setup_identity' in r['params']})
    return (*TECHNICAL, *DAILY, *TRADE, *(f'strat_{s}' for s in strategies), *(f'sec_{s}' for s in SECTORS),
            *FEATURE_NAMES, *NUMERIC_FEATURES, *(f'timeframe_{m}' for m in (1, 5, 15, 30)),
            *(f'param_{key}' for key in numeric), *(f'param_setup_{name}' for name in setups))


class FeatureRows:
    def __init__(self, bars, context, technical, tv, daily, *, symbol, security_id, sector):
        if isinstance(sector, DatedSectors):
            if sector.security_id != security_id:
                raise ValueError('Dated sector security identity differs')
        elif sector is not None and sector not in SECTORS:
            raise ValueError('Explicit frozen sector taxonomy required')
        if tuple(technical.columns) != TECHNICAL or tuple(tv.columns) != FEATURE_NAMES:
            raise ValueError('Technical/TV feature schema is incomplete')
        if not technical.index.equals(bars.index) or len(tv.index.difference(bars.index)):
            raise ValueError('Technical/TV observations differ from original chart history')
        required = {*DAILY, 'source_date', 'security_id'}
        if not required.issubset(daily.columns) or daily.index.tz is None:
            raise ValueError('Complete daily feature schema with aware availability timestamps required')
        if daily.index.has_duplicates or not daily.index.is_monotonic_increasing:
            raise ValueError('Daily information must have distinct ordered availability')
        if not symbol or not security_id or not daily.security_id.eq(security_id).all():
            raise ValueError('Daily context must belong to the explicit security identity')
        self.bars, self.context, self.technical, self.tv, self.daily = bars, context, technical, tv, daily
        self.sector = sector
        self.symbol, self.security_id = symbol, security_id
        self.averages = {}
        self.variants = {r['variant_id']: r for r in registered_catalog(['_rows'])['records']}

    def _average(self, window):
        if window not in self.averages:
            self.averages[window] = self.bars.Close.rolling(window).mean()
        return self.averages[window]

    def row(self, *, variant, bar_at, right, target_dte, bars_since_previous_signal, ticks,
            raw_spot, raw_spot_available_ns):
        if self.variants.get(variant['variant_id']) != variant or variant['signal_minutes'] != self.context['minutes']:
            raise ValueError('Unknown or mismatched parameter/timeframe identity')
        if right not in ('C', 'P') or type(target_dte) is not int or not 1 <= target_dte <= 9:
            raise ValueError('Explicit side and actual-short-DTE target required')
        if type(bars_since_previous_signal) is not int or bars_since_previous_signal < 0:
            raise ValueError('Nonnegative causal signal gap required')
        bar_at = pd.Timestamp(bar_at)
        if bar_at.tz is None or bar_at not in self.tv.index:
            raise ValueError('Original completed feature observation required')
        decision = bar_at + pd.Timedelta(minutes=variant['signal_minutes'])
        sector_record = self.sector.at(decision) if isinstance(self.sector, DatedSectors) else None
        sector = sector_record['sector'] if sector_record is not None else self.sector
        if (ticks.get('option_tick_status') != 'covered' or ticks.get('decision_close_ns') != decision.value
                or ticks.get('symbol') != self.symbol
                or ticks.get('window_start_ns') != bar_at.value or ticks.get('window_end_ns') != decision.value
                or not set(NUMERIC_FEATURES).issubset(ticks)):
            raise ValueError('Exact covered tick feature window required')
        from options.data.provider import parse_occ_symbol
        root, expiry, tick_right, strike = parse_occ_symbol(ticks['contract'])
        if root != self.symbol.replace('.', '') or tick_right != right:
            raise ValueError('Tick contract identity/direction differs from the proposal')
        actual_dte = (expiry - decision.tz_convert('America/New_York').date()).days
        if not 1 <= actual_dte <= 9:
            raise ValueError('Selected feature contract requires actual 1–9 calendar DTE')
        if (isinstance(raw_spot, bool) or not isinstance(raw_spot, (int, float))
                or not math.isfinite(raw_spot) or raw_spot <= 0
                or type(raw_spot_available_ns) is not int
                or not 0 <= decision.value - raw_spot_available_ns <= 60_000_000_000):
            raise ValueError('Fresh causally available raw spot required')
        daily_pos = self.daily.index.searchsorted(decision, side='right') - 1
        if daily_pos < 0:
            # A March 15 cold start has no March 14 feature state. Preserve
            # the requested start with visible NaNs, not a discarded row or
            # the final daily observation via pandas' negative indexing.
            daily = pd.Series({k: np.nan for k in DAILY})
        else:
            daily = self.daily.iloc[daily_pos]
            if pd.Timestamp(daily.source_date).date() >= decision.tz_convert('America/New_York').date():
                raise ValueError('Daily features require strictly prior-date observations')
        values = {**self.technical.loc[bar_at].to_dict(), **self.tv.loc[bar_at].to_dict(),
                  **{k: daily[k] for k in DAILY}, **{k: ticks[k] for k in NUMERIC_FEATURES}}
        if variant['strategy'] == 'ma':
            fast = self._average(variant['params']['fast_window']).loc[bar_at]
            slow = self._average(variant['params']['slow_window']).loc[bar_at]
            price = self.bars.Close.loc[bar_at]
            values.update(ma_gap=(fast - slow) / price, px_vs_fast=price / fast - 1)
        values.update(dir_short=float(right == 'P'), dte_frac=actual_dte / 9.,
                      moneyness=math.log(strike / raw_spot), bars_since_signal=math.log1p(bars_since_previous_signal))
        for name in schema():
            if name.startswith('strat_'):
                values[name] = float(name[6:] == variant['strategy'])
            elif name.startswith('sec_'):
                values[name] = float(name[4:] == sector)
            elif name.startswith('timeframe_'):
                values[name] = float(int(name[10:]) == variant['signal_minutes'])
            elif name.startswith('param_setup_'):
                values[name] = float(name[12:] == variant['params'].get('setup_identity'))
            elif name.startswith('param_'):
                values[name] = variant['params'].get(name[6:], np.nan)
        result = pd.Series({k: np.nan if pd.isna(values[k]) else float(values[k]) for k in schema()}, dtype=float)
        if np.isinf(result.to_numpy()).any():
            raise ValueError('Infinite model feature')
        result.attrs.update(symbol=self.symbol, security_id=self.security_id, variant_id=variant['variant_id'],
                            decision_ns=decision.value,
                            daily_available_at=self.daily.index[daily_pos].isoformat() if daily_pos >= 0 else None,
                            daily_context_status='available' if daily_pos >= 0 else 'warmup_unavailable',
                            sector_context=sector_record,
                            sector_context_status='dated' if sector_record is not None else 'static_component_fixture',
                            tick_request_id=ticks.get('request_id'), row_contract=ROW_CONTRACT,
                            contract=ticks['contract'], target_dte=target_dte, actual_dte=actual_dte,
                            raw_spot=raw_spot, raw_spot_available_ns=raw_spot_available_ns)
        return result
