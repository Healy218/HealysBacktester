from datetime import date,timedelta
from nn_meta.etfe.exact_windows import subtract,nearest,choices
from nn_meta.etfe.eligibility import observation_candidates
import pandas as pd


def test_subtraction_unions_duplicates_preserves_nanosecond_edges():
    assert subtract((10,100),[(10,20),(15,40),(70,101),(70,101)])==[(40,70)]
    assert subtract((10,100),[(0,10),(100,110)])==[(10,100)]


def test_fast_nearest_matches_contract_order_and_prior_date_guard():
    day=date(2024,1,18);records={};source=[]
    for dte in range(7):
        for k in (80,85,90,100,110,115,120):
            for suffix in ('A','B'):
                s=f'{dte}-{k}-{suffix}';expiry=day+timedelta(days=dte)
                r=dict(symbol=s,underlying='SPY',right='call',strike=k,expiration_date=expiry,first_date=day-timedelta(days=1))
                records[s]=r
                source.append(dict(symbol=s,right='call',strike=k,expiration_date=str(expiry),first_observed_at=pd.Timestamp('2024-01-17T15:00Z')))
    records['new']=dict(symbol='new',underlying='SPY',right='call',strike=100,expiration_date=day,first_date=day)
    groups=choices(records,'SPY',day,'call')
    assert all(s!='new' for rows in groups.values() for _,s in rows)
    for spot in (70,95,100,105,125,200):
        for target in (0,1,2,4,5):
            expected=observation_candidates(source,pd.Timestamp('2024-01-18T15:00Z'),right='call',target=target,spot=spot)
            assert nearest(groups,day,target,spot)==(expected[0]['symbol'] if expected else None)
