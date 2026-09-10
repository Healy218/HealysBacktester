from datetime import datetime, timezone
import pytest

from nn_meta.live.broker_fees import accounting, entry_line, profile, quote_pnl_line, side_fees

EQUITY='TEST351016P00005000'
NOW=datetime(2026,9,10,14,tzinfo=timezone.utc)


def test_equity_entry_and_sell_regulatory_fees():
    buy=side_fees(EQUITY,5,.09,'buy',gold=True)
    sell=side_fees(EQUITY,5,.09,'sell',gold=True)
    assert buy==dict(orf_occ=.20,cat=0.,broker=0.,exchange=0.,sec=0.,taf=0.,total=.20)
    assert sell['sec']==.01 and sell['taf']==.02 and sell['total']==.23
    result=accounting({'contract':EQUITY},5,.09,.10)
    assert result['entry_cost']==45.20 and result['net_proceeds']==49.77 and result['net_pnl']==4.57
    assert result['net_return']==pytest.approx(4.57/45.20)


def test_robinhood_published_spxw_example():
    assert side_fees('SPXW261016C06000000',12,.99,'sell',gold=True)['total']==10.68
    assert side_fees('SPXW261016C06000000',12,.99,'sell',gold=False)['total']==12.48


@pytest.mark.parametrize('root,premium,quantity,expected',[
    ('SPX',.99,1,.57),('SPX',1,1,.66),('SPXW',.99,1,.50),('SPXW',1,1,.59),
    ('DJX',1,9,0),('DJX',1,10,.70),('XSP',1,10,.70),('MRUT',1,10,.70),
    ('NDX',24.99,1,.25),('NDXP',25,1,.50),('XND',1,1,0),
    ('VIX',.10,1,.10),('VIXW',.11,1,.25),('VIX',1,1,.40),('VIX',2,1,.45),
    ('RUT',1,1,.18),('RUTW',1,1,.18),('MGTN',1,1,.16),('CBTX',1,1,.50),('MBTX',1,1,.25),
])
def test_index_tiers_and_sec_taf_exemptions(root,premium,quantity,expected):
    fees=side_fees(root+'261016C00010000',quantity,premium,'sell',gold=True)
    assert fees['exchange']==expected
    assert fees['sec']==fees['taf']==0
    assert fees['broker']==pytest.approx(.35*quantity)


def test_dow_company_options_are_not_dow_index_options():
    fees=side_fees('DOW261016P00025000',5,1,'sell',gold=True)
    assert fees['broker']==fees['exchange']==0 and fees['sec']>0


def test_rounding_subcent_waivers_and_taf_cap():
    assert side_fees(EQUITY,2,.09,'sell')['taf']==0
    assert side_fees(EQUITY,3,.09,'sell')['taf']==0
    assert side_fees(EQUITY,4,.09,'sell')['taf']==.01
    assert side_fees(EQUITY,33,.09,'buy')['cat']==0
    assert side_fees(EQUITY,50,.09,'buy')['cat']==.02
    assert side_fees(EQUITY,10000,.09,'sell')['taf']==9.79
    assert side_fees(EQUITY,1,1,'sell')['sec']==.01  # options have no $500 exemption


def test_missing_fills_or_index_account_tier_are_not_zero_fees(monkeypatch):
    monkeypatch.delenv('ROBINHOOD_GOLD',raising=False)
    assert accounting({'contract':EQUITY},None,.09) is None
    assert accounting({'contract':EQUITY},5,None) is None
    assert accounting({'contract':'SPX261016C06000000'},5,.09) is None
    monkeypatch.setenv('ROBINHOOD_GOLD','true')
    assert profile()['gold'] is True
    assert accounting({'contract':'SPX261016C06000000'},5,.09) is not None


def test_fresh_bid_pnl_and_stale_or_invalid_quote_omission():
    q=dict(bid=.10,ask=.11,ts=NOW.isoformat())
    text=quote_pnl_line({'contract':EQUITY},5,.09,q,NOW)
    assert '$+4.57' in text and '10.1%' in text and '$0.43' in text
    for bad in ({'ts':'2026-09-10T13:00:00+00:00'},{'bid':0},{'bid':.12},{'bid':float('nan')}):
        assert not quote_pnl_line({'contract':EQUITY},5,.09,q|bad,NOW)


def test_sell_list_and_taken_confirmation_include_estimated_entry_cost(tmp_path):
    from tests.test_taken_trades import queued,message
    from nn_meta.live.taken_trades import handle
    q,ident=queued(tmp_path)
    assert 'Estimated entry cost: $45.20' in handle(q,message(f'/taken {ident} 5 @ .09',2),'123')
    assert 'incl. $0.20 fees' in handle(q,message('/selllist',3),'123')
