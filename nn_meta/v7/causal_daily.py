"""Cold-start daily context from raw closes and reviewed effective actions.

Callers must supply reviewed identity spans and complete action evidence. These
calculations do not establish that provenance themselves or admit a full stage.
No vendor-adjusted history, forward-filled surface or missing-session return is
used. Chart-adjusted returns are features, not a dividend cash/P&L ledger.
"""
import numpy as np
import pandas as pd

from nn_meta.v7.causal_prices import PriceAction
from nn_meta.v7.scope import require_research_window

FEATURES = ('rvol_5', 'rvol_21', 'atm_iv_near', 'atm_iv_far', 'term_slope',
            'iv_chg_5', 'pc_ratio', 'market_iv', 'rv_iv_spread', 'beta_60d')


def timeline(calendar, start, end):
    require_research_window(start, end)
    if start < calendar.start or end > calendar.end:
        raise ValueError('Calendar must cover the complete requested interval')
    sessions = sorted(calendar.sessions)
    days = [day for day in sessions if start <= day <= end]
    if not days:
        raise ValueError('At least one source session required')
    openings, closings, available = [], [], []
    positions = {day: position for position, day in enumerate(sessions)}
    for day in days:
        position = positions[day]
        if position + 1 >= len(sessions):
            raise ValueError('Captured next-session availability required')
        opening, closing = calendar.bounds(day)
        openings.append(opening.tz_localize('UTC').value)
        closings.append(closing.tz_localize('UTC').value)
        available.append(calendar.bounds(sessions[position + 1])[0].tz_localize('UTC').value)
    return pd.DataFrame(dict(source_date=days, session_open_ns=openings,
                             stock_available_ns=closings, available_ns=available))


def returns(stock, actions, calendar, *, security_id, start, end, action_evidence_identity):
    """One identity's complete calendar panel, with explicit continuity spans.

    A missing span means identity is unknown on that day. Separate reviewed
    spans must have separate nonempty IDs; returning to a prior span is invalid.
    ``actions`` must include all effective events in the requested interval;
    ``action_evidence_identity`` binds that upstream reviewed inventory, including
    its no-event intervals. Merely passing an empty list is not evidence.
    """
    clock = timeline(calendar, start, end)
    needed = {'source_date', 'raw_close', 'observed_minutes', 'available_ns', 'identity_span'}
    if (not isinstance(security_id, str) or not security_id
            or not isinstance(action_evidence_identity, str) or not action_evidence_identity
            or not needed.issubset(stock)):
        raise ValueError('Explicit security, action evidence and raw daily facts required')
    stock = stock.sort_values('source_date').reset_index(drop=True)
    if stock.source_date.tolist() != clock.source_date.tolist():
        raise ValueError('Every captured calendar day must be explicit exactly once')
    if ('security_id' in stock and not stock.security_id.eq(security_id).all()
            or not pd.api.types.is_integer_dtype(stock.available_ns)
            or stock.available_ns.isna().any()
            or not stock.available_ns.eq(clock.stock_available_ns).all()):
        raise ValueError('Stock security identity or completed-session clocks differ')
    if (not pd.api.types.is_integer_dtype(stock.observed_minutes)
            or stock.observed_minutes.isna().any() or stock.observed_minutes.lt(0).any()):
        raise ValueError('Integer nonnegative minute observation counts required')
    observed = stock.observed_minutes.gt(0)
    if (not np.isfinite(stock.loc[observed, 'raw_close']).all()
            or stock.loc[observed, 'raw_close'].le(0).any()
            or stock.loc[~observed, 'raw_close'].notna().any()):
        raise ValueError('Missing/observed raw prices disagree')
    # Normalize nullable string columns so comparisons with missing spans are
    # concrete booleans, including the first row and a post-gap return.
    span = stock.identity_span.astype(object).where(stock.identity_span.notna(), None)
    if any(not isinstance(v, str) or not v for v in span.dropna()):
        raise ValueError('Named reviewed continuity spans required')
    boundaries = span.ne(span.shift()) | span.isna()
    seen = set()
    for value in span[boundaries].dropna():
        if value in seen:
            raise ValueError('Disjoint histories cannot reuse a continuity span')
        seen.add(value)
    actions = list(actions)
    if (not all(isinstance(a, PriceAction) for a in actions)
            or len({a.event_id for a in actions}) != len(actions)
            or len({a.effective_at for a in actions}) != len(actions)):
        raise ValueError('Unique typed actions required; combine simultaneous events upstream')
    factors = np.ones(len(stock)); event_ids = [None] * len(stock)
    for action in actions:
        day = action.effective_at.tz_convert('America/New_York').date().isoformat()
        if not start <= day <= end:
            # Out-of-window evidence cannot change a prefix or its feature state.
            continue
        positions = np.flatnonzero(clock.source_date.eq(day))
        if len(positions) != 1 or action.effective_at.value != clock.session_open_ns.iloc[positions[0]]:
            raise ValueError('Actions must take effect at captured regular-session opens')
        position = positions[0]
        if pd.isna(span.iloc[position]):
            raise ValueError('Effective action has no reviewed security continuity')
        factors[position] = action.price_factor
        event_ids[position] = action.event_id
    valid = observed & observed.shift(1, fill_value=False) & span.notna() & span.eq(span.shift())
    # Local adjacent ratios avoid an unstable cumulative adjusted-price series.
    log_returns = np.log(stock.raw_close) - np.log(stock.raw_close.shift()) - np.log(factors)
    log_returns = log_returns.where(valid)
    with np.errstate(over='ignore', invalid='ignore'):
        simple = np.expm1(log_returns)
    if np.isinf(simple).any() or np.isinf(log_returns).any():
        raise ValueError('Unrepresentable causal daily return')
    result = clock.copy()
    result['security_id'] = security_id
    result['identity_span'] = span
    result['raw_close'] = stock.raw_close
    result['observed_minutes'] = stock.observed_minutes
    result['action_id'] = event_ids
    result['action_factor'] = factors
    result['action_evidence_identity'] = action_evidence_identity
    result['return_valid'] = valid
    result['return_status'] = np.select(
        [span.isna(), ~observed, boundaries, ~observed.shift(1, fill_value=False)],
        ['unknown_identity', 'no_stock_observation', 'continuity_start', 'missing_prior_session'],
        default='observed')
    result['simple_return'] = simple
    result['log_return'] = log_returns
    for window in (5, 21):
        result[f'rvol_{window}'] = log_returns.rolling(window, min_periods=window).std(ddof=1) * np.sqrt(252)
    result.attrs.update(return_basis='raw adjacent closes adjusted only for reviewed effective actions',
                        missing_policy='no fill; no bridging sessions or continuity spans', research_ready=False)
    return result


def context(daily_returns, surfaces, *, market=None, is_market=False):
    """Project all ten model daily features; market returns use the same contract.

    Inputs are complete source-session panels, joined by date rather than row
    position. Market context must already be calculated with this function.
    All resulting rows retain exact next-opening availability for FeatureRows.
    """
    required = {'source_date', 'security_id', 'identity_span', 'available_ns', 'simple_return',
                'rvol_5', 'rvol_21', 'return_valid', 'raw_close'}
    if (not required.issubset(daily_returns) or daily_returns.empty
            or daily_returns.source_date.duplicated().any()
            or daily_returns.security_id.isna().any()
            or daily_returns.security_id.nunique() != 1
            or not pd.api.types.is_integer_dtype(daily_returns.available_ns)
            or daily_returns.available_ns.isna().any()
            or np.isinf(daily_returns[['simple_return', 'rvol_5', 'rvol_21']].to_numpy()).any()):
        raise ValueError('Complete single-security causal daily returns required')
    needed = {'source_date', 'atm_iv_near', 'atm_iv_far', 'pc_ratio', 'capture_complete', 'available_ns'}
    if (not needed.issubset(surfaces) or surfaces.source_date.duplicated().any()
            or not pd.api.types.is_bool_dtype(surfaces.capture_complete)
            or not surfaces.capture_complete.eq(True).all()):
        raise ValueError('Complete unique observed daily surface captures required')
    result = daily_returns.sort_values('source_date').set_index('source_date').copy()
    surface = surfaces.set_index('source_date').sort_index()
    if (not surface.index.equals(result.index)
            or not pd.api.types.is_integer_dtype(surface.available_ns)
            or not surface.available_ns.eq(result.available_ns).all()):
        raise ValueError('Surface dates or next-session availability differ')
    if 'security_id' in surface and not surface.security_id.eq(result.security_id).all():
        raise ValueError('Surface security identity differs')
    for name in ('atm_iv_near', 'atm_iv_far', 'pc_ratio'):
        values = surface[name]
        if np.isinf(values.to_numpy()).any() or values.dropna().lt(0).any():
            raise ValueError('Invalid surface feature')
        # Do not propagate a literal ticker surface through an unknown identity.
        result[name] = (values.clip(upper=5) if name == 'pc_ratio' else values).where(result.identity_span.notna())
    result['term_slope'] = result.atm_iv_far - result.atm_iv_near
    runs = (result.identity_span.ne(result.identity_span.shift()) | result.identity_span.isna()).cumsum()
    result['iv_chg_5'] = result.groupby(runs).atm_iv_near.diff(5)
    if is_market:
        if market is not None:
            raise ValueError('Market reference cannot also supply another market')
        reference = result
    else:
        if market is None:
            raise ValueError('Explicit causal market context required')
        if (not {'source_date', 'simple_return', 'atm_iv_near', 'available_ns', 'security_id'}.issubset(market)
                or market.source_date.duplicated().any() or market.security_id.isna().any()
                or market.security_id.nunique() != 1
                or not pd.api.types.is_integer_dtype(market.available_ns)
                or np.isinf(market[['simple_return', 'atm_iv_near']].to_numpy()).any()):
            raise ValueError('Complete single-reference market panel required')
        reference = market.set_index('source_date').reindex(result.index)
        if not reference.available_ns.eq(result.available_ns).all():
            raise ValueError('Market dates or availability differ')
    market_returns = reference.simple_return
    result['market_iv'] = reference.atm_iv_near
    result['beta_60d'] = result.simple_return.rolling(60).cov(market_returns) / market_returns.rolling(60).var().replace(0., np.nan)
    result['rv_iv_spread'] = result.rvol_21 - result.atm_iv_near
    if np.isinf(result[list(FEATURES)].to_numpy()).any():
        raise ValueError('Infinite daily feature')
    result['source_date'] = result.index
    result.index = pd.DatetimeIndex(pd.to_datetime(result.available_ns, unit='ns', utc=True), name='available_at')
    if not result.index.is_unique or not result.index.is_monotonic_increasing:
        raise ValueError('Unique increasing daily availability required')
    result.attrs.update(daily_contract='v7-causal-daily-v1', surface_policy='no forward fill; put/call capped at 5',
                        availability='next captured regular open', research_ready=False)
    return result


def missingness(frame):
    """Inspect warmup and unresolved missingness without filtering out any row."""
    return {name: dict(missing=int(frame[name].isna().sum()),
                      first_source_date=(str(frame.loc[frame[name].notna(), 'source_date'].iloc[0])
                                         if frame[name].notna().any() else None),
                      first_available_at=(frame[name].first_valid_index().isoformat()
                                          if frame[name].notna().any() else None)) for name in FEATURES}
