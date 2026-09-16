"""Listed-exchange daily identity capture contracts; no price or OTC requests."""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from nn_meta.v7.action_inventory import iso_day

EXCHANGES = ('ARCX', 'BATS', 'XASE', 'XNAS', 'XNYS')
ENDPOINT = 'https://api.massive.com/v3/reference/tickers'


def query(day, exchange):
    iso_day(day)
    if exchange not in EXCHANGES:
        raise ValueError('Explicit listed exchange required; OTC excluded')
    return dict(market='stocks',locale='us',date=day,exchange=exchange,
                active='true',limit=1000,sort='ticker',order='asc')


def page_records(body, exchange, seen):
    records = body.get('results', [] if body.get('count') == 0 else None)
    if body.get('status') != 'OK' or not isinstance(records,list) or len(records)>1000:
        raise ValueError('Invalid bounded identity page')
    if body.get('count') is not None and body['count'] != len(records):
        raise ValueError('Identity response count differs')
    for row in records:
        symbol=row.get('ticker')
        if (not isinstance(symbol,str) or not symbol or symbol in seen
                or row.get('primary_exchange') != exchange or row.get('market') != 'stocks'
                or row.get('locale') != 'us' or row.get('active') is not True):
            raise ValueError('Duplicate or out-of-scope listed identity')
        seen.add(symbol)
    return records


def next_page(url):
    parsed=urlsplit(url)
    if (parsed.scheme!='https' or parsed.netloc!='api.massive.com'
            or parsed.path!='/v3/reference/tickers' or parsed.username or parsed.password or parsed.fragment):
        raise ValueError('Identity pagination changed origin or endpoint')
    params=[(k,v) for k,v in parse_qsl(parsed.query) if k.lower()!='apikey']
    if not any(k=='cursor' and v for k,v in params):
        raise ValueError('Identity pagination requires a cursor')
    return urlunsplit((parsed.scheme,parsed.netloc,parsed.path,urlencode(params),''))
