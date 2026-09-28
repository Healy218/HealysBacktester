"""Sealed historical option aggregates alongside the existing V6 tick adapter."""
from pathlib import Path
import re
import pandas as pd
from nn_meta.live.v6_market import MassiveMarket
from .storage import identity,seal,verify,sha


class ResearchMarket(MassiveMarket):
    def get_contract_bars(self,occ_symbol,start,end,interval):
        occ=occ_symbol.removeprefix('O:')
        if not re.fullmatch(r'[A-Z]+\d{6}[CP]\d{8}',occ) or interval!='15m':
            raise ValueError('expected plain OCC and frozen 15m interval')
        request=dict(contract=occ,start=str(start),end=str(end),interval=interval)
        root=self.root/'aggregates'/identity(request)
        if (root/'complete.json').exists():
            verify(root,request)
        else:
            root.mkdir(parents=True,exist_ok=True)
            rows,evidence=self.pages(f'/v2/aggs/ticker/O:{occ}/range/15/minute/{start}/{end}',
                                    dict(adjusted='true',sort='asc',limit=50000))
            frame=pd.DataFrame(rows)
            if frame.empty:
                bars=pd.DataFrame(columns=['Open','High','Low','Close','Volume'],
                                  index=pd.DatetimeIndex([],name='timestamp'))
            else:
                bars=frame.rename(columns=dict(o='Open',h='High',l='Low',c='Close',v='Volume'))
                bars.index=pd.to_datetime(frame.t,unit='ms',utc=True).dt.tz_localize(None)
                bars=bars[['Open','High','Low','Close','Volume']].sort_index()
                if bars.index.has_duplicates:raise ValueError('duplicate option aggregate timestamps')
            bars.to_parquet(root/'bars.parquet')
            seal(root,request,['bars.parquet'],provider=evidence)
        self.evidence.append(dict(path=str(root/'complete.json'),sha256=sha(root/'complete.json'),kind='option_aggregate'))
        return pd.read_parquet(root/'bars.parquet')
