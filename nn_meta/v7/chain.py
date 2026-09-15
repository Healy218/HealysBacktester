"""Select V7 standard-root contracts using only prior-date observations."""
from __future__ import annotations


class ObservedChain:
    def __init__(self,path,symbol):
        from nn_meta.v7.runtime import configure_threads
        configure_threads(1)
        import polars as pl
        from collections import OrderedDict
        self.symbol=symbol.replace('.', '')
        rows=pl.scan_parquet(path).filter(pl.col('root')==self.symbol).collect().to_dicts()
        self.expiry_rows={}
        for row in rows:
            self.expiry_rows.setdefault((row['expiry'],row['right']),[]).append(row)
        self.expiries=sorted({key[0] for key in self.expiry_rows})
        for key in self.expiry_rows:
            self.expiry_rows[key].sort(key=lambda r:(r['strike'],r['ticker']))
        self.cache=OrderedDict()

    def select(self,day,raw_spot,right,target_dte):
        return self.select_many(day,[raw_spot],right,target_dte)[0]

    def select_many(self,day,raw_spots,right,target_dte):
        """Vectorized nearest strikes, preserving expiry and tie ordering exactly."""
        import bisect
        from datetime import timedelta
        import numpy as np
        if right not in ('C','P') or type(target_dte) is not int or not 1<=target_dte<=9:
            raise ValueError('Explicit side and 1–9 target required')
        spots=np.asarray(raw_spots,dtype=float)
        if spots.ndim!=1 or not np.isfinite(spots).all() or (spots<=0).any():
            raise ValueError('Positive raw spots required')
        key=day,right
        if key not in self.cache:
            first=bisect.bisect_right(self.expiries,day)
            last=bisect.bisect_right(self.expiries,day+timedelta(days=9))
            groups={}
            for expiry in self.expiries[first:last]:
                # Collapse equal strikes to the lexically first ticker after
                # applying the prior-date observation requirement.
                by_strike={}
                for r in self.expiry_rows.get((expiry,right),[]):
                    if r['first_seen']<day:
                        by_strike.setdefault(r['strike'],r)
                if by_strike:
                    groups[expiry]=(np.array(list(by_strike),dtype=float),list(by_strike.values()))
            self.cache[key]=groups
            if len(self.cache)>128:
                self.cache.popitem(last=False)
        self.cache.move_to_end(key)
        groups=self.cache[key]
        output=[None]*len(spots)
        pending=np.ones(len(spots),dtype=bool)
        for expiry in sorted(groups,key=lambda e:(abs((e-day).days-target_dte),e)):
            strikes,records=groups[expiry]
            hi=np.clip(np.searchsorted(strikes,spots),0,len(strikes)-1)
            lo=np.clip(hi-1,0,len(strikes)-1)
            chosen=np.where(np.abs(strikes[lo]-spots)<=np.abs(strikes[hi]-spots),lo,hi)
            eligible=pending & (strikes[chosen]>=.85*spots) & (strikes[chosen]<=1.15*spots)
            for i in np.flatnonzero(eligible):
                output[i]=records[chosen[i]]
            pending[eligible]=False
            if not pending.any():
                break
        return output
