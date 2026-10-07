import datetime as dt

import pytest

from nn_meta.etfe import existence_census as e, option_daily_capture as o

P=dict(symbols='SPY240119C00470000,SPY240119P00470000',timeframe='1Day',start='2024-01-01T05:00:00+00:00',
       end='2024-01-20T04:59:59+00:00',sort='asc',limit=10000)


def test_daily_job_validation():
    assert o.job('option_daily_bars',P,'x')['route']=='option_daily_bars'
    for bad in (dict(P,timeframe='1Min'),dict(P,symbols='IWM240119C00470000'),dict(P,symbols=','.join(['SPY240119C00470000']*2)),
                dict(P,end='2026-10-04T00:00:00+00:00')):
        with pytest.raises(ValueError):o.job('option_daily_bars',bad,'x')


def test_rows_reject_foreign_symbol_and_out_of_range():
    item=o.job('option_daily_bars',P,'x');bar=dict(t='2024-01-10T05:00:00Z',o=1,h=1,l=1,c=1,v=3,n=1,vw=1)
    body=dict(bars={'SPY240119C00470000':[bar]},next_page_token=None)
    assert len(list(o.rows(body,item)))==1
    with pytest.raises(ValueError):list(o.rows(dict(bars={'QQQ240119C00400000':[bar]},next_page_token=None),item))
    with pytest.raises(ValueError):list(o.rows(dict(bars={'SPY240119C00470000':[dict(bar,t='2024-02-01T05:00:00Z')]},next_page_token=None),item))


def test_existence_usable_from_next_session():
    days=[dt.date(2024,1,d) for d in (17,18,19,22)]
    got=e.available_from({'A':dt.date(2024,1,18),'B':dt.date(2024,1,19),'C':dt.date(2024,1,22)},days)
    assert got=={'A':dt.date(2024,1,19),'B':dt.date(2024,1,22),'C':None}


def test_selection_v2_choices_respect_existence_and_dte():
    from nn_meta.etfe import selection_v2 as s
    day=dt.date(2024,3,4)
    index={('SPY','call',dt.date(2024,3,4)):[(510.0,'A',dt.date(2024,3,1)),(511.0,'B',dt.date(2024,3,5))],
           ('SPY','call',dt.date(2024,3,11)):[(510.0,'C',dt.date(2024,3,1))]}
    assert s.choices(index,'SPY',day,'call')=={dt.date(2024,3,4):[(510.0,'A')]}
    assert s.targets('SPY')==(0,1,5,2,4) and s.targets('VOO')==(0,1,5)


def test_envelope_jobs_group_by_expiry_and_bound_windows():
    from nn_meta.etfe import envelope_capture as c
    syms=[f'SPY240119C{i:08d}' for i in range(150)]
    demand=dict(bars={s:[1705674600000000000+i,1705698000000000000] for i,s in enumerate(syms)},
                meta={s:['SPY','call','2024-01-19'] for s in syms},
                quotes_itm=[['SPY','2024-01-19T15:44:30-05:00','2024-01-19T15:45:00-05:00']]*2,quotes_liq=[])
    jobs=c.bar_jobs(demand)
    assert [len(j['params']['symbols'].split(',')) for j in jobs]==[100,50]
    assert jobs[0]['params']['start']=='2024-01-19T14:30:00+00:00' and jobs[0]['params']['end'].startswith('2024-01-19T20:59:59')
    q=c.quote_jobs(demand)
    assert len(q)==1 and q[0]['params']['start']=='2024-01-19T20:44:30+00:00'
