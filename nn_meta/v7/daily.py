"""Daily V7 surface/context features with explicit raw spot and availability.

The fixed-rate Black–Scholes inputs are the existing baseline's engineering
assumptions, not claims about historically observed rates or American exercise.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SurfacePolicy:
    maximum_dte: int = 45
    minimum_premium: float = .20
    risk_free_rate: float = .0425
    dividend_yield: float = .012
    near_atm_log_band: float = .01

    def __post_init__(self):
        if (type(self.maximum_dte) is not int or self.maximum_dte < 1
                or not all(np.isfinite(v) for v in (self.minimum_premium, self.risk_free_rate,
                                                    self.dividend_yield, self.near_atm_log_band))
                or self.minimum_premium < 0 or self.near_atm_log_band <= 0):
            raise ValueError('Invalid declared surface policy')


def surface_day(symbol, day, options, raw_spot, *, policy=SurfacePolicy()):
    from nn_options_signal.build_dataset import implied_vol, bs_price
    import re
    if not np.isfinite(raw_spot) or raw_spot <= 0:
        raise ValueError('Contemporaneous raw daily spot is required')
    wanted = options.ticker.str.fullmatch('O:' + re.escape(symbol.replace('.', '')) + r'\d{6}[CP]\d{8}')
    frame = options.loc[wanted, ['ticker', 'close', 'volume']].copy()
    if frame.ticker.duplicated().any():
        raise ValueError('Duplicate contract/day observations')
    frame['expiry'] = pd.to_datetime(frame.ticker.str[-15:-9], format='%y%m%d')
    frame['right'] = frame.ticker.str[-9]
    frame['strike'] = frame.ticker.str[-8:].astype(float) / 1000
    frame['dte'] = (frame.expiry - pd.Timestamp(day)).dt.days
    if (not np.isfinite(frame[['close', 'volume', 'strike']].to_numpy()).all()
            or (frame[['close', 'volume']] < 0).any().any() or (frame.strike <= 0).any()):
        raise ValueError('Invalid option daily observations')
    frame = frame[(frame.dte >= 1) & (frame.dte <= policy.maximum_dte) &
                  (frame.close >= policy.minimum_premium) & (frame.strike > 0)]
    atm = frame[np.abs(np.log(frame.strike / raw_spot)) < policy.near_atm_log_band].copy()
    if len(atm):
        price, strike, tenor, calls = atm.close.to_numpy(), atm.strike.to_numpy(), atm.dte.to_numpy() / 365., (atm.right == 'C').to_numpy()
        atm['iv'] = implied_vol(price, np.full(len(atm), raw_spot), strike, tenor, calls,
                               r=policy.risk_free_rate, q=policy.dividend_yield)
        high = bs_price(raw_spot, strike, tenor, 5., policy.risk_free_rate, policy.dividend_yield, calls)
        atm.loc[price > high, 'iv'] = np.nan
    else:
        atm['iv'] = pd.Series(dtype=float)
    volumes = frame.groupby('right').volume.sum()
    ratio = volumes.get('P', np.nan) / volumes.get('C', np.nan) if volumes.get('C', 0) > 0 else np.nan
    return {'source_date': day, 'atm_iv_near': float(atm.loc[atm.dte <= 20, 'iv'].median()),
            'atm_iv_far': float(atm.loc[atm.dte > 20, 'iv'].median()), 'pc_ratio': float(ratio),
            'option_contract_observations': len(frame), 'capture_complete': True}


def daily_context(stock, surfaces, calendar, *, security_id, market=None, is_market=False):
    """One security, complete captured dates; gaps never become invented returns."""
    required = {'source_date', 'raw_close', 'adjusted_close'}
    if not required.issubset(stock) or stock.source_date.duplicated().any():
        raise ValueError('Unique raw/adjusted daily stock observations required')
    if not security_id or not len(stock):
        raise ValueError('Explicit nonempty security history required')
    if not np.isfinite(stock[['raw_close', 'adjusted_close']].to_numpy()).all() or (stock[['raw_close', 'adjusted_close']] <= 0).any().any():
        raise ValueError('Observed daily stock prices must be positive and finite')
    stock = stock.sort_values('source_date').set_index('source_date')
    days = sorted(d for d in calendar.sessions if stock.index[0] <= d <= stock.index[-1])
    stock = stock.reindex(days)
    if (surfaces.source_date.duplicated().any() or not pd.api.types.is_bool_dtype(surfaces.capture_complete)
            or not surfaces.capture_complete.eq(True).all()):
        raise ValueError('Complete unique daily aggregate captures required')
    surf = surfaces.set_index('source_date').reindex(days)
    if surf.capture_complete.isna().any():
        raise ValueError('Missing aggregate day cannot be disguised by forward-filled IV')
    result = stock.copy()
    returns = result.adjusted_close.pct_change(fill_method=None)
    log_returns = np.log(result.adjusted_close).diff()
    result['rvol_5'] = log_returns.rolling(5).std() * np.sqrt(252)
    result['rvol_21'] = log_returns.rolling(21).std() * np.sqrt(252)
    for field in ('atm_iv_near', 'atm_iv_far', 'pc_ratio'):
        values = surf[field].clip(0, 5) if field == 'pc_ratio' else surf[field]
        result[field] = values.ffill()
        result[field + '_observed_on'] = pd.Series(days, index=days).where(values.notna()).ffill()
    result['term_slope'] = result.atm_iv_far - result.atm_iv_near
    result['iv_chg_5'] = result.atm_iv_near.diff(5)
    if market is None:
        if is_market is not True:
            raise ValueError('Non-market securities require explicit market context')
        market_returns = returns
        result['market_iv'] = result.atm_iv_near
    else:
        market = market.set_index('source_date').reindex(days)
        market_returns = market.adjusted_close.pct_change(fill_method=None)
        result['market_iv'] = market.atm_iv_near
    result['beta_60d'] = returns.rolling(60).cov(market_returns) / market_returns.rolling(60).var().replace(0, np.nan)
    result['rv_iv_spread'] = result.rvol_21 - result.atm_iv_near
    result['source_date'] = days
    result['security_id'] = security_id
    available = []
    for day in days:
        following = next((d for d in sorted(calendar.sessions) if d > day), None)
        if following is None:
            raise ValueError('Calendar must include next-session availability')
        available.append(calendar.bounds(following)[0].tz_localize('UTC'))
    result.index = pd.DatetimeIndex(available, name='available_at')
    result.attrs.update(availability_policy='next regular open from captured calendar',
                        option_surface_spot='raw', return_basis='declared adjusted history',
                        rate_policy='fixed baseline proxy; not observed historical rates', research_ready=False)
    return result
