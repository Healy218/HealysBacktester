"""Select V7 standard-root contracts using only prior-date observations."""
from __future__ import annotations


class ObservedChain:
    def __init__(self,path,symbol):
        from nn_meta.v7.runtime import configure_threads
        configure_threads(1)
        import polars as pl
        self.symbol=symbol
        self.rows=pl.scan_parquet(path).filter(pl.col('root')==symbol).collect().to_dicts()
        self.cache={}

    def select(self,day,raw_spot,right,target_dte):
        import math
        if right not in ('C','P') or type(target_dte) is not int or not 1<=target_dte<=9:
            raise ValueError('Explicit side and 1–9 target required')
        if not math.isfinite(raw_spot) or raw_spot<=0:raise ValueError('Positive raw spot required')
        key=day,right
        if key not in self.cache:
            self.cache[key]=[r for r in self.rows if r['first_seen']<day and r['right']==right
                             and 1<=(r['expiry']-day).days<=9]
        eligible=[r for r in self.cache[key] if .85*raw_spot<=r['strike']<=1.15*raw_spot]
        if not eligible:return None
        expiry=min({r['expiry'] for r in eligible},key=lambda e:(abs((e-day).days-target_dte),e))
        return min((r for r in eligible if r['expiry']==expiry),key=lambda r:(abs(r['strike']-raw_spot),r['strike'],r['ticker']))
