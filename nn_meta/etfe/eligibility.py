"""Point-in-time selection guard: observations never stand in for dated terms."""
from dataclasses import dataclass
from datetime import date
import math
import pandas as pd


@dataclass(frozen=True)
class DatedTerms:
    symbol: str
    effective_at: pd.Timestamp
    ends_at: pd.Timestamp
    available_at: pd.Timestamp
    evidence_sha256: str
    multiplier: float
    strike: float
    expiry_close: pd.Timestamp

    def __post_init__(self):
        for name in ('effective_at','ends_at','available_at','expiry_close'):
            t=pd.Timestamp(getattr(self,name))
            if pd.isna(t) or t.tzinfo is None:raise ValueError('Dated terms require aware clocks')
            object.__setattr__(self,name,t)
        if self.effective_at>=self.ends_at or self.available_at>self.ends_at:
            raise ValueError('Invalid terms interval')
        if (len(self.evidence_sha256)!=64 or any(c not in '0123456789abcdef' for c in self.evidence_sha256)
                or not math.isfinite(self.multiplier) or self.multiplier<=0
                or not math.isfinite(self.strike) or self.strike<=0):
            raise ValueError('Positive economics and evidence hash required')


def observation_candidates(contracts, at, *, right, target, spot):
    """Acquisition-only candidates; never turn today's status/OI into eligibility."""
    at=pd.Timestamp(at)
    if at.tzinfo is None or not math.isfinite(spot) or spot<=0:raise ValueError('Aware decision and positive spot required')
    if target not in (0,1,2,4,5):raise ValueError('Unknown purchase target')
    day=at.tz_convert('America/New_York').date();choices=[]
    for c in contracts:
        first=pd.Timestamp(c['first_observed_at'])
        if first.tzinfo is None:raise ValueError('Aware first observation required')
        expiry=date.fromisoformat(c['expiration_date']);dte=(expiry-day).days
        if c['right']!=right or not 0<=dte<=5:continue
        if first.tz_convert('America/New_York').date()>=day:continue
        if not .85*spot<=c['strike']<=1.15*spot:continue
        choices.append(dict(c,actual_dte=dte))
    return sorted(choices,key=lambda c:(abs(c['actual_dte']-target),c['expiration_date'],
        abs(c['strike']-spot),c['strike'],c['symbol']))


def select_contract(contracts, at, *, right, target, spot, terms=(),
                    discovery_complete=False, source_admitted=False,weekly_eligible=False):
    at=pd.Timestamp(at)
    candidates=observation_candidates(contracts,at,right=right,target=target,spot=spot)
    proposed=candidates[0] if candidates else None
    base=dict(acquisition_candidate=proposed,selected_contract=None,entry_eligible=False)
    if target in (2,4) and not weekly_eligible:return dict(base,reason='weekly_listing_evidence_unresolved')
    if not candidates:return dict(base,reason='no_prior_date_observed_candidate')
    if discovery_complete is not True:return dict(base,reason='historical_discovery_unresolved')
    if source_admitted is not True:return dict(base,reason='source_provenance_unresolved')
    eligible=[]
    for c in candidates:
        found=[t for t in terms if t.symbol==c['symbol'] and t.effective_at<=at<t.ends_at and t.available_at<=at]
        if len(found)>1:raise ValueError('Ambiguous dated terms')
        if not found:return dict(base,reason='dated_terms_or_expiry_clock_unresolved')
        t=found[0]
        if t.strike!=c['strike'] or str(t.expiry_close.tz_convert('America/New_York').date())!=c['expiration_date']:
            raise ValueError('Dated contract identity mismatch')
        if at>=t.expiry_close-pd.Timedelta(minutes=15):continue
        eligible.append(c)
    if not eligible:return dict(base,reason='dated_terms_or_expiry_clock_unresolved')
    # Ordering is unchanged by future prices or missing feature/fill windows.
    return dict(base,selected_contract=eligible[0]['symbol'],entry_eligible=False,
                selection_eligible=True,reason='selection_only_signal_price_cash_checks_still_required')


def feature_window(at, minutes):
    at=pd.Timestamp(at)
    if at.tzinfo is None or minutes not in (1,5,15):raise ValueError('Aware signal and ETFE timeframe required')
    return at-pd.Timedelta(minutes=minutes+1),at-pd.Timedelta(minutes=1)


def union_intervals(intervals):
    merged=[]
    for a,b in sorted(intervals):
        if a>=b:raise ValueError('Nonempty half-open interval required')
        if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
        else:merged.append((a,b))
    return merged
