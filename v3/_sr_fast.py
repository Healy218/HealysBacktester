# SPDX-License-Identifier: MPL-2.0
# Same ordered numerical recurrence as tv_sr_channels.py (LonesomeTheBlue,
# Ej53t8Wv publication 6); optional compiled evaluation, no fastmath.
import numpy as np
from numba import njit
from v3._pine_fast import rounded as cmp


@njit(cache=True)
def pivot(values, bar, period, high):
    if bar < 2 * period: return np.nan
    at = bar - period
    value = cmp(values[at])
    for j in range(at-period, at):
        if (cmp(values[j]) > value if high else cmp(values[j]) < value): return np.nan
    for j in range(at+1,bar+1):
        if (cmp(values[j]) >= value if high else cmp(values[j]) <= value): return np.nan
    return values[at]


@njit(cache=True)
def channels(high, low, close, src_high, src_low, period, width_percent, minimum_strength, max_channels, lookback):
    pivots, locations = [], []
    levels, strengths = np.zeros((10,2)), np.zeros(10)
    output = np.full((len(high),39),np.nan)
    for i in range(len(high)):
        ph, pl = pivot(src_high,i,period,True), pivot(src_low,i,period,False)
        has_high, has_low = not np.isnan(ph) and ph != 0, not np.isnan(pl) and pl != 0
        width = (high[max(0,i-299):i+1].max()-low[max(0,i-299):i+1].min())*width_percent/100
        if has_high or has_low:
            pivots.insert(0,ph if has_high else pl); locations.insert(0,i)
            while len(locations) and i-locations[-1]>lookback:
                locations.pop(); pivots.pop()
            candidates=np.zeros((len(pivots),3))
            for at,anchor in enumerate(pivots):
                hi=lo=anchor; strength=0
                for other in pivots:
                    distance=hi-other if cmp(other)<=cmp(hi) else other-lo
                    if cmp(distance)<=cmp(width):
                        if cmp(other)<=cmp(hi): lo=min(lo,other)
                        else: hi=max(hi,other)
                        strength+=20
                touches=0
                for j in range(max(0,i-lookback),i+1):
                    if (cmp(high[j])<=cmp(hi) and cmp(high[j])>=cmp(lo)) or (cmp(low[j])<=cmp(hi) and cmp(low[j])>=cmp(lo)):
                        touches+=1
                candidates[at,0]=float(strength+touches); candidates[at,1]=hi; candidates[at,2]=lo
            levels[:,:]=0.; strengths[:]=0.; slot=0
            for _ in pivots:
                best_value,best_index=-1.,-1
                for j in range(len(candidates)):
                    strength=candidates[j,0]
                    if strength>best_value and strength>=minimum_strength*20:
                        best_value,best_index=strength,j
                if best_index>=0:
                    strength,hi,lo=candidates[best_index,0],candidates[best_index,1],candidates[best_index,2]
                    levels[slot,0]=hi; levels[slot,1]=lo; strengths[slot]=strength
                    for j in range(len(candidates)):
                        if cmp(lo)<=cmp(candidates[j,1])<=cmp(hi) or cmp(lo)<=cmp(candidates[j,2])<=cmp(hi): candidates[j,0]=-1.
                    slot+=1
                    if slot>=10: break
            for x in range(9):
                for y in range(x+1,10):
                    if strengths[y]>strengths[x]:
                        strengths[y]=strengths[x]
                        for z in range(2):
                            temp=levels[x,z]; levels[x,z]=levels[y,z]; levels[y,z]=temp
        inside=False
        for j in range(max_channels):
            if cmp(levels[j,1])<=cmp(close[i])<=cmp(levels[j,0]): inside=True
        bull,bear=False,False
        if i and not inside:
            for j in range(max_channels):
                if cmp(close[i-1])<=cmp(levels[j,0]) and cmp(close[i])>cmp(levels[j,0]): bull=True
                if cmp(close[i-1])>=cmp(levels[j,1]) and cmp(close[i])<cmp(levels[j,1]): bear=True
        output[i,0]=ph; output[i,1]=pl
        output[i,2]=i-period if has_high or has_low else np.nan
        output[i,3]=has_high or has_low; output[i,4]=width; output[i,5]=len(pivots)
        output[i,6]=inside; output[i,7]=bull; output[i,8]=bear
        for j in range(10):
            output[i,9+3*j]=levels[j,0] if levels[j,0]!=0 else np.nan
            output[i,10+3*j]=levels[j,1] if levels[j,1]!=0 else np.nan
            output[i,11+3*j]=strengths[j]
    return output
