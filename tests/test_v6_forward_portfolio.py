import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from nn_meta.ev_sizing import ev_candidate_rows, ev_selected_rows
from nn_meta.live.v6_portfolio import ForwardPortfolio, checked_quote, choose, key_of
from nn_meta.session_calendar import SessionCalendar
from scripts.run_v6_forward import expiry_cutoff


class ForwardPortfolioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'book.sqlite3'
        self.book = ForwardPortfolio(self.path, scope={'frozen': 'test'})
        self.bar = pd.Timestamp('2026-09-14 13:30:00')
        self.now = pd.Timestamp('2026-09-14 13:46:00Z')
        self.contract = 'SPY261016C00760000'

    def tearDown(self):
        self.temp.cleanup()

    def rows(self):
        return pd.DataFrame([dict(symbol='SPY', strategy='x', entry_ts=self.bar, dte=30,
            decision=.2, score=.7, decision_contract=self.contract, option_tick_status='covered')])

    def quote(self, contract, *, after):
        return dict(contract=contract,bid=2.,ask=2.1,bid_size=10,ask_size=10,
            sip_timestamp_ns=(self.now - pd.Timedelta(seconds=1)).value,received_at=self.now.isoformat())

    def allocate(self, rows=None):
        rows = self.rows() if rows is None else rows
        return self.book.allocate(rows,bar=self.bar,now=self.now,quote_loader=self.quote,
            contexts={key_of(r): {} for r in rows.to_dict('records')},clock=lambda:self.now,alerts=True)

    def test_selection_matches_frozen_offline_allocator(self):
        rng=np.random.default_rng(871)
        rows=pd.DataFrame([dict(symbol=f'S{i%12}',strategy=f's{i//12}',trade_idx=0,dte=d,
            entry_ts=self.bar,exit_ts=self.bar+pd.Timedelta(days=1),net_return=.1,
            decision=float(rng.uniform(-.1,.9)),score=.7) for i in range(40) for d in [1,5,10,30,45]])
        offline=ev_selected_rows(ev_candidate_rows(rows,rows.decision,.05),5,.1)
        forward=choose(rows, set())
        self.assertEqual(offline.index.tolist(),forward.index.tolist())
        np.testing.assert_array_equal(offline.size_fraction,forward.size_fraction)

    def test_restart_deduplicates_positions_cycles_and_alerts(self):
        self.assertEqual(self.allocate()['opened'],1)
        self.book=ForwardPortfolio(self.path,scope={'frozen':'test'})
        self.assertTrue(self.allocate()['duplicate'])
        self.assertEqual(len(self.book.open_positions()),1)
        self.assertEqual(self.book.summary()['outbox'],{'pending':1})

    def test_no_quote_is_recorded_unfilled_without_replacement(self):
        rows=pd.concat([self.rows(),self.rows().assign(strategy='lower',decision=.1)])
        def fail(*a,**k): raise ValueError('no fresh quote')
        result=self.book.allocate(rows,bar=self.bar,now=self.now,quote_loader=fail,
            contexts={},clock=lambda:self.now)
        self.assertEqual(result['unfilled'],1)
        self.assertFalse(self.book.open_positions())

    def test_quote_validation_rejects_wrong_stale_crossed_and_future(self):
        for change in [dict(contract='QQQ261016C00500000'),dict(bid=3.),
                       dict(sip_timestamp_ns=(self.now-pd.Timedelta(seconds=31)).value),
                       dict(received_at=(self.now+pd.Timedelta(seconds=1)).isoformat()),dict(ask_size=0)]:
            q=self.quote(self.contract,after=self.now)
            q.update(change)
            with self.assertRaises(ValueError): checked_quote(q,self.contract,self.now,self.now-pd.Timedelta(minutes=1))

    def test_exit_frees_slot_and_realizes_ask_bid_costs_once(self):
        self.allocate()
        key=key_of(self.rows().iloc[0])
        self.book.trigger(key,kind='exit',reason='stop',at=self.now-pd.Timedelta(seconds=10))
        self.book.settle(key,quote_loader=self.quote,clock=lambda:self.now,alerts=True)
        expected=1+.1*(2*.9985/(2.1*1.0015)-1)
        self.assertAlmostEqual(self.book.summary()['equity'],expected)
        self.book.settle(key,quote_loader=self.quote,clock=lambda:self.now,alerts=True)
        self.assertAlmostEqual(self.book.summary()['equity'],expected)
        self.assertFalse(self.book.open_positions())

    def test_roll_sale_commits_before_failed_replacement_and_retries_once(self):
        self.allocate()
        key=key_of(self.rows().iloc[0]); replacement='SPY261120C00760000'
        self.book.trigger(key,kind='roll',reason='expiry cutoff',at=self.now-pd.Timedelta(seconds=10))
        def quote(contract,**kwargs):
            if contract==replacement: raise ValueError('replacement unavailable')
            return self.quote(contract,**kwargs)
        with self.assertRaisesRegex(ValueError,'replacement unavailable'):
            self.book.settle(key,quote_loader=quote,clock=lambda:self.now,replacement=replacement,alerts=True)
        pending=self.book.open_positions()[0]
        self.assertEqual(pending['state'],'roll_pending')
        self.assertEqual(len(pending['legs']),1)
        self.book.settle(key,quote_loader=self.quote,clock=lambda:self.now,replacement=replacement,alerts=True)
        live=self.book.open_positions()[0]
        self.assertEqual(live['state'],'open'); self.assertEqual(live['rolls'],1)
        self.assertEqual(len(live['legs']),1)
        self.assertEqual(live['contract'],replacement)

    def test_expiry_cutoff_respects_early_close_and_weekend_expiry(self):
        cal=SessionCalendar({'coverage_start':'2026-11-27','coverage_end':'2026-11-30','sessions':[
            {'date':'2026-11-27','open':'09:30','close':'13:00'}, {'date':'2026-11-30','open':'09:30','close':'16:00'}]})
        self.assertEqual(expiry_cutoff('AAPL261128C00200000',cal),pd.Timestamp('2026-11-27 17:45Z'))
        self.assertEqual(expiry_cutoff('SPY261128C00760000',cal),pd.Timestamp('2026-11-27 18:00Z'))
        self.assertEqual(expiry_cutoff('QQQ261130P00600000',cal),pd.Timestamp('2026-11-30 21:00Z'))
        self.assertEqual(expiry_cutoff('AAPL261130P00200000',cal),pd.Timestamp('2026-11-30 20:45Z'))

    def test_late_entry_and_changed_scope_fail_closed(self):
        self.now+=pd.Timedelta(minutes=6)
        with self.assertRaisesRegex(ValueError,'deadline'): self.allocate()
        with self.assertRaisesRegex(ValueError,'rules changed'): ForwardPortfolio(self.path,scope={'other':'scope'})

    def test_strategy_exit_during_roll_wait_releases_cash_without_another_sale(self):
        self.allocate(); key=key_of(self.rows().iloc[0])
        self.book.trigger(key,kind='roll',reason='expiry',at=self.now-pd.Timedelta(seconds=10))
        self.book.settle(key,quote_loader=self.quote,clock=lambda:self.now)
        self.assertEqual(self.book.open_positions()[0]['state'],'roll_pending')
        self.book.trigger(key,kind='exit',reason='strategy exit',at=self.now,alerts=True)
        self.assertFalse(self.book.open_positions())
        expected=1+.1*(2*.9985/(2.1*1.0015)-1)
        self.assertAlmostEqual(self.book.summary()['equity'],expected)
        self.book.trigger(key,kind='exit',reason='retry',at=self.now)
        self.assertAlmostEqual(self.book.summary()['equity'],expected)


if __name__=='__main__': unittest.main()
