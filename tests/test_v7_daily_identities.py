import pytest
from nn_meta.v7.daily_identities import query,page_records,next_page


def record(**change):
    return dict(ticker='ABC',primary_exchange='XNAS',market='stocks',locale='us',active=True,**change)


def test_listed_query_and_no_otc():
    assert query('2022-03-15','XNAS')['date']=='2022-03-15'
    with pytest.raises(ValueError):query('2022-03-15','OTCM')
    with pytest.raises(ValueError):query('2022-3-15','XNAS')


@pytest.mark.parametrize('change',[{'primary_exchange':'OTCM'},{'market':'otc'},{'active':False},
                                 {'locale':'ca'},{'ticker':''}])
def test_reject_out_of_scope_response(change):
    with pytest.raises(ValueError):page_records(dict(status='OK',results=[record()|change]),'XNAS',set())


def test_missing_figi_is_retained_and_cross_page_duplicate_rejected():
    seen=set();body=dict(status='OK',count=1,results=[record()])
    assert page_records(body,'XNAS',seen)==body['results']
    with pytest.raises(ValueError):page_records(body,'XNAS',seen)
    assert page_records(dict(status='OK',count=0),'XNAS',set())==[]
    with pytest.raises(ValueError):page_records(dict(status='OK'),'XNAS',set())
    with pytest.raises(ValueError):page_records(body|{'count':2},'XNAS',set())


def test_pagination_strips_credentials_and_rejects_changed_origins():
    assert next_page('https://api.massive.com/v3/reference/tickers?cursor=abc&apiKey=secret')=='https://api.massive.com/v3/reference/tickers?cursor=abc'
    for url in ['https://elsewhere.test/v3/reference/tickers?cursor=a',
                'http://api.massive.com/v3/reference/tickers?cursor=a',
                'https://api.massive.com/v2/aggs?cursor=a',
                'https://api.massive.com/v3/reference/tickers?apiKey=secret']:
        with pytest.raises(ValueError):next_page(url)
