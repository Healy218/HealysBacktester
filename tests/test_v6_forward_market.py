import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from datetime import date

import pandas as pd

from nn_meta.live.v6_market import MassiveMarket
from nn_meta.option_tick_dataset import request_id, compute_feature_row
from options.data.massive_ticks import canonical_bytes
from options.tick_features import window_features


class Response:
    status_code=200
    def __init__(self,body): self.body=body
    def json(self): return self.body


class Session:
    def __init__(self,bodies): self.bodies=iter(bodies); self.calls=[]
    def get(self,url,**kw): self.calls.append((url,kw)); return Response(next(self.bodies))


class MarketTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.now=pd.Timestamp('2026-09-14 13:46Z')
        self.contract='SPY261016C00760000'
    def tearDown(self): self.temp.cleanup()
    def market(self,bodies):
        return MassiveMarket(self.temp.name,session=Session(bodies),tick_client=object(),clock=lambda:self.now)

    def test_complete_pagination_and_secret_removal(self):
        m=self.market([{'status':'OK','results':[1],'next_url':'https://api.massive.com/v3/reference/options/contracts?cursor=a&apiKey=never-forward'}, {'status':'OK','results':[2]}])
        rows,receipt=m.pages('/v3/reference/options/contracts',{})
        self.assertEqual(rows,[1,2]); self.assertTrue(receipt['complete'])
        self.assertNotIn('apiKey',m.session.calls[1][1]['params'])

    def test_truncation_delay_cross_origin_rejected(self):
        for body in [{'status':'DELAYED','results':[]},
            {'status':'OK','results':[],'next_url':'https://evil.example/v3/reference/options/contracts'},
            {'status':'OK','results':[],'next_url':'https://api.massive.com/v3/reference/options/contracts?cursor=more'}]:
            with self.assertRaises(ValueError): self.market([body]).pages('/v3/reference/options/contracts',{},max_pages=1)

    def test_malformed_quote_and_no_quote_fail_closed(self):
        for rows in [[],[{'bid_price':2,'ask_price':1,'bid_size':1,'ask_size':1,'sip_timestamp':self.now.value-1000000000}]]:
            with self.assertRaises(ValueError):
                self.market([{'status':'OK','results':rows}]).execution_quote(self.contract,after=self.now-pd.Timedelta(minutes=1))

    def test_reference_adjusted_roots_follow_frozen_archive_grammar(self):
        row=dict(ticker='O:SPY261016C00760000',strike_price=760.,expiration_date='2026-10-16',shares_per_contract=100)
        adjusted=dict(row,ticker='O:SPY1261016C00010000')
        m=self.market([{'status':'OK','results':[adjusted,row]}])
        result=m.get_chain('SPY',right='C',expiration_gte=date(2026,9,15),expiration_lte=date(2026,11,3),as_of=date(2026,9,13))
        self.assertEqual([c.symbol for c in result],[self.contract])
        self.assertEqual(m.evidence[-1]['excluded_count'],1)

    def test_captured_features_equal_training_primitive_and_bind_bytes(self):
        start=pd.Timestamp('2026-09-14 13:30Z').value; end=start+900000000000
        req=dict(symbol='SPY',contract=self.contract,window_start_ns=start,window_end_ns=end,decision_close_ns=end)
        req['request_id']=request_id(req)
        quotes=[dict(sip_timestamp=start+1,bid_price=2.,ask_price=2.1,bid_size=20,ask_size=10,sequence_number=1),
                dict(sip_timestamp=end-1000000000,bid_price=2.2,ask_price=2.3,bid_size=10,ask_size=20,sequence_number=2)]
        trades=[dict(sip_timestamp=start+1000000000,price=2.1,size=4,conditions=[209],sequence_number=3),
                dict(sip_timestamp=start+2000000000,price=2.,size=7,conditions=[233],sequence_number=4)]
        class Ticks:
            def capture(inner,contract,kind,start_ns,end_ns,max_pages):
                rows=quotes if kind=='quotes' else trades
                return rows,dict(schema='massive-option-ticks-v1',provider='massive',contract='O:'+contract,
                    kind=kind,start_ns=start_ns,end_ns=end_ns,complete=True,records=len(rows),
                    records_sha256=hashlib.sha256(canonical_bytes(rows)).hexdigest(),retrieved_at=self.now.isoformat())
        m=MassiveMarket(self.temp.name,session=Session([]),tick_client=Ticks(),clock=lambda:self.now)
        policy=dict(availability='sip',condition_namespace='massive_integer',allowed_trade_conditions=[209],max_quote_age_ns=30000000000)
        actual=m.tick_features(req,policy)
        kw=dict(start_ns=start,end_ns=end,coverage_start_ns=start,coverage_end_ns=end,complete=True,
            availability='sip',max_quote_age_ns=30000000000,allowed_trade_conditions=[209],allow_unconditioned_trades=False)
        expected=compute_feature_row(window_features(quotes,trades,**kw),req,eligible=window_features(quotes,trades[:1],**kw))
        self.assertEqual(actual,expected)
        self.assertEqual(actual['eligible_contract_volume'],4)
        self.assertEqual(actual['condition_excluded_contract_volume'],7)
        record=next(Path(self.temp.name).rglob('quotes.json.gz')); record.write_bytes(b'corrupted')
        m._features.clear()
        with self.assertRaisesRegex(ValueError,'changed'): m.tick_features(req,policy)


if __name__=='__main__': unittest.main()
