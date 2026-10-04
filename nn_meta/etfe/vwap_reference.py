"""ETFE completed-minute VWAP references, not an order-fill simulator."""
from datetime import datetime, timedelta, timezone
import math

BASIS = 'etfe-option-completed-1min-vwap-v1'
BAR_SECONDS = 60
AVAILABILITY_LAG_SECONDS = 1
MAX_BAR_END_AGE_SECONDS = 60


def utc_time(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Reference timestamps must be timezone-aware')
    return value.astimezone(timezone.utc)


def reference_from_bar(bar, *, as_of, available_at=None):
    """Consume a single Alpaca 1Min option bar in raw API field names.

    Caller owns contract/session/feed/1Min provenance and bar selection. Final
    historical bars have unknown original arrival/revision time: end + 1 second
    is an explicit model assumption, never a measured provider delivery claim.
    When a captured availability timestamp exists, honor whichever time is later.
    Missing bars and stale/future observations give no reference; malformed or
    zero-activity bars fail explicitly. Never use high/low, close or forward-fill
    as fallback, and never manufacture quotes or fills from the returned price.
    """
    decision = utc_time(as_of)
    if bar is None:
        return None
    start = utc_time(bar['t'])
    if start.second or start.microsecond:
        raise ValueError('Expected a minute-aligned 1Min bar timestamp')
    end = start + timedelta(seconds=BAR_SECONDS)
    earliest = end + timedelta(seconds=AVAILABILITY_LAG_SECONDS)
    known = max(earliest, utc_time(available_at)) if available_at is not None else earliest
    if decision < known or decision > end + timedelta(seconds=MAX_BAR_END_AGE_SECONDS):
        return None
    for field in ('vw', 'v', 'n'):
        value = bar.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f'Expected positive finite {field}; no fallback permitted')
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f'Expected positive finite {field}; no fallback permitted')
    if not float(bar['v']).is_integer() or not float(bar['n']).is_integer():
        raise ValueError('Contract volume and trade count must be integers')
    return dict(basis=BASIS, price=float(bar['vw']), volume=bar['v'], trade_count=bar['n'],
        bar_start=start.isoformat(), bar_end=end.isoformat(), available_at=known.isoformat(),
        as_of=decision.isoformat(), bar_end_age_seconds=(decision-end).total_seconds(),
        availability_basis='captured_with_minimum_lag' if available_at is not None else 'modeled_end_plus_1s',
        original_revision_timing_verified=False, executable_fill_verified=False)
