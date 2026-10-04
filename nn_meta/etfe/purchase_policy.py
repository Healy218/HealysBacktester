"""ETFE calendar-DTE purchase guard; independent of any old market data."""
from datetime import date, datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT/'docs/specs/ETFE_SCOPE_ALPACA_20261004.json'


def load_scope():
    scope = json.loads(SCOPE.read_text())
    if (scope['schema'] != 'etfe-research-scope-v3' or scope['actual_calendar_dte'] != [1,5]
            or scope['dte_targets']['default'] != [1,5] or scope['dte_targets']['weekly_subset'] != [2,4]
            or scope['symbols'] != ['SPY','QQQ','VOO'] or scope['options_provider'] != 'alpaca'
            or scope['ready_for_build'] or scope['training_authorized']):
        raise ValueError('Expected current unadmitted Alpaca-only 1–5 DTE scope')
    return scope


def purchase_dte(expiration_date, attempt_at):
    """Calendar dates in New York, recomputed at each actual purchase/roll attempt."""
    expiry = date.fromisoformat(expiration_date)
    stamp = datetime.fromisoformat(attempt_at.replace('Z','+00:00')) if isinstance(attempt_at,str) else attempt_at
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('Purchase attempt needs a timezone-aware timestamp')
    return (expiry-stamp.astimezone(ZoneInfo('America/New_York')).date()).days


def check_purchase(expiration_date, attempt_at, *, target, weekly_eligible=False):
    """DTE check only: true does not bypass price, terms, cash or timing guards."""
    scope = load_scope()
    targets = scope['dte_targets']['default'] + (scope['dte_targets']['weekly_subset'] if weekly_eligible else [])
    dte = purchase_dte(expiration_date, attempt_at)
    if target not in targets:
        return dict(dte_eligible=False, actual_calendar_dte=dte, reason='target_not_enabled')
    if not scope['actual_calendar_dte'][0] <= dte <= scope['actual_calendar_dte'][1]:
        return dict(dte_eligible=False, actual_calendar_dte=dte, reason='outside_1_to_5_calendar_dte')
    return dict(dte_eligible=True, actual_calendar_dte=dte, reason='dte_guard_passed')


def dte_fraction(expiration_date, attempt_at):
    """Versioned ETFE v3 feature scale; only eligible purchase dates may use it."""
    dte = purchase_dte(expiration_date, attempt_at)
    if not 1 <= dte <= 5:
        raise ValueError('DTE feature requested outside purchase range')
    return dte/5.0
