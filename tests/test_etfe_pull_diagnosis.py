"""Offline regression checks for diagnostic pagination and trade reconciliation."""
from scripts.diagnose_etfe_alpaca_pulls import aggregate, pages


class Client:
    def __init__(self, bodies, status=200):
        self.bodies = iter(bodies)
        self.receipts = []
        self.queries = []
        self.status = status

    def get(self, route, params):
        self.queries.append(dict(params))
        receipt = dict(status_code=self.status, transport_error=None)
        self.receipts.append(receipt)
        return receipt, next(self.bodies)


def test_short_and_empty_pages_continue_and_duplicate_occurrences_survive():
    row = dict(t='2024-01-18T14:30:00.001Z', p=1, s=1, c='I')
    client = Client([
        dict(trades={'QQQ': [row]}, next_page_token='a'),
        dict(trades={}, next_page_token='b'),
        dict(trades={'QQQ': [row], 'SPY': [row]}, next_page_token=None),
    ])
    result = pages(client, 'option_trades', {'limit': 10000}, 'trades')
    assert result['complete']
    assert result['records'] == {'QQQ': [row, row], 'SPY': [row]}
    assert client.queries == [{'limit': 10000}, {'limit': 10000, 'page_token': 'a'},
                              {'limit': 10000, 'page_token': 'b'}]


def test_repeated_token_is_incomplete():
    client = Client([dict(trades={}, next_page_token='a')] * 2)
    result = pages(client, 'option_trades', {}, 'trades')
    assert not result['complete']
    assert result['reason'] == 'repeated_token'


def test_page_cap_does_not_claim_empty_history():
    client = Client([dict(trades={}, next_page_token='a')])
    result = pages(client, 'option_trades', {}, 'trades', max_pages=1)
    assert not result['complete']
    assert result['reason'] == 'page_cap'


def test_request_error_is_incomplete():
    client = Client([{'message': 'unexpected query parameter(s): feed'}], status=400)
    result = pages(client, 'option_trades', {}, 'trades')
    assert not result['complete']
    assert result['reason'] == 'request_failed'


def test_volume_only_and_excluded_conditions_do_not_change_price_vwap():
    rows = [dict(t='2024-01-18T14:30:00Z', p=p, s=s, c=c)
            for p, s, c in [(1, 2, 'I'), (3, 2, 'f'), (50, 100, 't'),
                            (50, 100, 'u'), (500, 1000, 'A')]]
    bar = aggregate(rows)['2024-01-18T14:30:00Z']
    assert (bar['o'], bar['c'], bar['h'], bar['l'], bar['vw']) == (1, 3, 3, 1, 2)
    assert (bar['v'], bar['n'], bar['vwap_volume']) == (204, 4, 4)
    assert not bar['unknown']


def test_unknown_condition_is_visible_and_identical_trades_are_counted():
    row = dict(t='2024-01-18T14:30:00Z', p=1.13, s=3, c='I')
    bar = aggregate([row, row, dict(row, c='?')])['2024-01-18T14:30:00Z']
    assert bar['v'] == 6
    assert bar['n'] == 2
    assert bar['unknown'] == ['?']
