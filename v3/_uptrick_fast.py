# SPDX-License-Identifier: CC-BY-SA-4.0
# Compiled recurrence from tv_uptrick.py, Uptrick f4N0F439/v1. Same numerical
# order and thresholds, no fastmath; historical Python path remains available.
import numpy as np
from numba import njit
from v3._pine_fast import rounded as cmp


@njit(cache=True)
def states(chop,bull_votes,bear_votes,regime,gate,bull_price_ok,bear_price_ok,momentum,efficiency,
           fast_bull,fast_bear,medium_bull,medium_bear,slow_bull,slow_bear):
    n=len(chop)
    state=np.zeros(n,np.int64); counters=np.zeros((n,4),np.int64)
    ready=np.zeros((n,2),np.bool_); strong=np.zeros((n,2),np.bool_)
    bull_st_bars=bear_st_bars=bull_confirm=bear_confirm=trend=0
    last_flip=-1
    for i in range(n):
        ch,bv,sv=cmp(chop[i]),bull_votes[i],bear_votes[i]
        votes=3 if ch>.70 else 2
        bull_st_bars=min(bull_st_bars+1,5) if bv>=votes else 0
        bear_st_bars=min(bear_st_bars+1,5) if sv>=votes else 0
        persistence=2 if ch>.72 else 1
        bull_candidate=cmp(regime[i])>cmp(gate[i]) and bull_price_ok[i] and cmp(momentum[i])>.025 and bull_st_bars>=persistence
        bear_candidate=cmp(regime[i])<cmp(-gate[i]) and bear_price_ok[i] and cmp(momentum[i])<-.025 and bear_st_bars>=persistence
        required=3 if ch>.72 else 2 if ch>.40 else 1
        bull_confirm=min(bull_confirm+1,4) if bull_candidate else 0
        bear_confirm=min(bear_confirm+1,4) if bear_candidate else 0
        strong_bull=bull_candidate and bv==3 and cmp(regime[i])>cmp(gate[i]+.26) and cmp(momentum[i])>.16 and cmp(efficiency[i])>.42
        strong_bear=bear_candidate and sv==3 and cmp(regime[i])<cmp(-(gate[i]+.26)) and cmp(momentum[i])<-.16 and cmp(efficiency[i])>.42
        bull_ready=(bull_confirm>=required or strong_bull) and fast_bull[i] and (medium_bull[i] or slow_bull[i])
        bear_ready=(bear_confirm>=required or strong_bear) and fast_bear[i] and (medium_bear[i] or slow_bear[i])
        cooldown=6+int(np.floor(chop[i]*4.+.5))
        done=(100000 if last_flip<0 else i-last_flip)>=cooldown
        changed=False
        if trend!=1 and bull_ready and (done or strong_bull): trend=1; changed=True
        elif trend!=-1 and bear_ready and (done or strong_bear): trend=-1; changed=True
        if changed:
            last_flip=i; bull_confirm=bear_confirm=bull_st_bars=bear_st_bars=0
        state[i]=trend
        counters[i,0]=bull_st_bars; counters[i,1]=bear_st_bars; counters[i,2]=bull_confirm; counters[i,3]=bear_confirm
        ready[i,0]=bull_ready; ready[i,1]=bear_ready; strong[i,0]=strong_bull; strong[i,1]=strong_bear
    return state,counters,ready,strong
