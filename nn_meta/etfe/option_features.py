"""Registered option trade/bar formulas; diagnostic values never confer admission."""
from collections import Counter
import math
import numbers

import numpy as np
import pandas as pd

MINUTE=60_000_000_000
ALLOW=frozenset('HIJSabcdefghijklmnopqrs')
NAMES=['etfe_option_'+x for x in ('trade_range_bps','trade_size_cv','traded_bar_fraction',
    'bar_end_age_seconds','traded_bars_per_second','trade_count_per_second',
    'trade_volume_per_second','vwap_last_bps','tickrule_signed_volume_fraction',
    'tickrule_classified_volume_fraction')]
TRADE=[NAMES[i] for i in (0,1,5,6,7,8,9)]
BAR=[NAMES[i] for i in (2,3,4)]


def integer(value):
    if isinstance(value,bool) or not isinstance(value,numbers.Integral):raise ValueError('Integer nanosecond clock required')
    return int(value)


def positive(value):
    return isinstance(value,numbers.Real) and not isinstance(value,bool) and math.isfinite(value) and value>0


def empty_proven(proof,start,end,at):
    if not proof:return False
    h=proof.get('evidence_sha256','')
    return (len(h)==64 and all(c in '0123456789abcdef' for c in h)
        and integer(proof['start_ns'])<=start<end<=integer(proof['end_ns'])
        and integer(proof['available_at_ns'])<=at)


def compute_window(symbol,at,minutes,trades,bars,coverage):
    """Use terminal transport plus observed minutes for final-vintage diagnostics.

    Unobserved minutes require explicit dated no-trade evidence to become zeros.
    Caller retains source/capture lineage; received_at is NOT publication time.
    Optional available_at_ns can delay, never advance, modeled event/end + 1s.
    All returned values are unadmitted diagnostics even with complete fixtures.
    """
    at=pd.Timestamp(at)
    if at.tzinfo is None or minutes not in (1,5,15) or at.value%MINUTE:raise ValueError('Aware aligned ETFE decision required')
    end=at.value-MINUTE;start=end-minutes*MINUTE;decision=at.value
    values={n:None for n in NAMES};reasons={n:'uncomputed' for n in NAMES}
    selected=[];bar_selected=[];seen=set();native=set();counts=Counter();excluded_volume=0.
    def choose(rows,route):
        result=[]
        for r in rows:
            if r['symbol']!=symbol:continue
            t=integer(r['timestamp_ns'])
            if not start<=t<end:continue
            oid=r.get('occurrence_id')
            if oid is not None:
                key=(route,oid)
                if key in seen:raise ValueError('Repeated source occurrence')
                seen.add(key)
            result.append(r)
        return result
    selected=choose(trades,'trade');bar_selected=choose(bars,'bar')
    trade_by_minute=Counter(integer(r['timestamp_ns'])//MINUTE*MINUTE for r in selected)
    bar_by_minute=Counter(integer(r['timestamp_ns']) for r in bar_selected)
    if any(t%MINUTE for t in bar_by_minute):raise ValueError('Unaligned option bar')
    trade_issue=bar_issue=None
    for t in range(start,end,MINUTE):
        c=coverage.get(t,{})
        for kind,present in (('trade',trade_by_minute[t]),('bar',bar_by_minute[t])):
            proof=c.get(kind+'_empty_evidence')
            if proof and present and empty_proven(proof,t,t+MINUTE,decision):raise ValueError('Empty evidence conflicts with observations')
            issue=None
            if c.get(kind+'_transport_complete') is not True:issue='uncaptured_window'
            elif not present and not empty_proven(proof,t,t+MINUTE,decision):issue='unresolved_absence'
            if kind=='trade' and issue:trade_issue=trade_issue or issue
            if kind=='bar' and issue:bar_issue=bar_issue or issue
    eligible=[]
    for r in selected:
        condition=r.get('condition');counts['observed']+=1
        if condition not in ALLOW:
            counts['excluded_condition']+=1
            if positive(r.get('size')):excluded_volume+=r['size']
            continue
        counts['condition_allowed']+=1
        if r.get('quality_flags') or not positive(r.get('price')) or not positive(r.get('size')):
            trade_issue=trade_issue or 'invalid_trade';continue
        native_id=r.get('native_trade_id')
        if native_id is not None:
            if native_id in native:trade_issue=trade_issue or 'unresolved_trade_revision'
            native.add(native_id)
        t=integer(r['timestamp_ns']);available=max(t+1_000_000_000,integer(r.get('available_at_ns',t+1_000_000_000)))
        if available>decision:trade_issue=trade_issue or 'not_yet_available';counts['unavailable']+=1;continue
        eligible.append(r)
    eligible.sort(key=lambda r:integer(r['timestamp_ns']))
    valid_bars=[]
    for r in bar_selected:
        t=integer(r['timestamp_ns'])
        if bar_by_minute[t]>1:bar_issue=bar_issue or 'ambiguous_bar_vintage';continue
        if r.get('quality_flags') or not all(positive(r.get(k)) for k in ('vwap','volume','trade_count')):
            bar_issue=bar_issue or 'invalid_bar';continue
        available=max(t+MINUTE+1_000_000_000,integer(r.get('available_at_ns',t+MINUTE+1_000_000_000)))
        if available>decision:bar_issue=bar_issue or 'not_yet_available';continue
        valid_bars.append(r)
    if trade_issue:
        for n in TRADE:reasons[n]=trade_issue
    else:
        for n in TRADE:reasons[n]='empty_eligible_window'
        values[NAMES[5]]=len(eligible)/(60*minutes)
        values[NAMES[6]]=sum(r['size'] for r in eligible)/(60*minutes)
        reasons[NAMES[5]]=reasons[NAMES[6]]='observed_diagnostic'
        if eligible:
            prices=np.array([r['price'] for r in eligible],dtype='float64');sizes=np.array([r['size'] for r in eligible],dtype='float64')
            vwap=math.fsum(r['price']*r['size'] for r in eligible)/sum(r['size'] for r in eligible)
            values[NAMES[0]]=float(10000*(prices.max()-prices.min())/vwap)
            values[NAMES[1]]=float(sizes.std(ddof=0)/sizes.mean())
            reasons[NAMES[0]]=reasons[NAMES[1]]='observed_diagnostic'
            last=[r['price'] for r in eligible if r['timestamp_ns']==eligible[-1]['timestamp_ns']]
            if len(set(last))==1:
                values[NAMES[7]]=float(10000*(vwap-last[0])/last[0]);reasons[NAMES[7]]='observed_diagnostic'
            else:reasons[NAMES[7]]='ambiguous_last_trade'
            if len({r['timestamp_ns'] for r in eligible})!=len(eligible):
                reasons[NAMES[8]]=reasons[NAMES[9]]='ambiguous_order'
            else:
                signs=np.zeros(len(eligible));sign=0
                for i in range(1,len(eligible)):
                    if prices[i]!=prices[i-1]:sign=np.sign(prices[i]-prices[i-1])
                    signs[i]=sign
                values[NAMES[8]]=float(np.dot(signs,sizes)/sizes.sum())
                values[NAMES[9]]=float(sizes[signs!=0].sum()/sizes.sum())
                reasons[NAMES[8]]=reasons[NAMES[9]]='observed_diagnostic'
    if bar_issue:
        for n in BAR:reasons[n]=bar_issue
    else:
        values[NAMES[2]]=len(valid_bars)/minutes;values[NAMES[4]]=len(valid_bars)/(60*minutes)
        reasons[NAMES[2]]=reasons[NAMES[4]]='observed_diagnostic'
        if valid_bars:
            values[NAMES[3]]=(decision-max(r['timestamp_ns']+MINUTE for r in valid_bars))/1e9
            reasons[NAMES[3]]='observed_diagnostic'
        else:reasons[NAMES[3]]='no_traded_bar'
    if any(v is not None and not math.isfinite(v) for v in values.values()):raise ValueError('Nonfinite diagnostic')
    return dict(values=values,missing={n:int(values[n] is None) for n in NAMES},reasons=reasons,
        audit=dict(counts,excluded_condition_volume=excluded_volume,eligible_observed=len(eligible)),
        feature_start_ns=start,feature_end_ns=end,model_feature_admitted=False,
        admission_reason='dated_selection_session_condition_provenance_unresolved')
