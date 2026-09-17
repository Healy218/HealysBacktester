"""Bounded, proposal-driven contract selection and causal tick-feature demand.

This is the pre-entry feature capture stage. Execution, minute marks and rolls
need their own demands; these requests never establish full quote coverage.
"""
from itertools import groupby
import json
from pathlib import Path
import sqlite3

import pandas as pd

from nn_meta.v7.proposal_store import _disk
from nn_meta.v7.storage import identity, sha, verify, receipt, transaction

TARGETS = (1, 2, 4, 5, 7)
FORMAT = 'v7-proposal-entry-demand-v1'


def selection_id(symbol, decision_ns, right, target_dte):
    return identity(dict(schema=FORMAT, symbol=symbol, decision_ns=int(decision_ns),
                         right=right, target_dte=target_dte))


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def _parents(stores, chain_root):
    result = {}
    def add(values):
        for path, digest in values.items():
            if path in result and result[path] != digest:
                raise ValueError('Conflicting entry-demand parent bindings')
            result[path] = digest
    for store in stores:
        store.features.verify_bindings()
        for root in (store.path, store.features.path):
            for path in root.rglob('complete.json'):
                document = verify(path.parent)
                add({str(path):sha(path)})
                add({str(path.parent/name):digest for name,digest in document['files'].items()})
        add(store.features.declaration['inputs'])
        add(store.features.declaration['sources'])
    doc = verify(chain_root)
    add({str(chain_root/'complete.json'):sha(chain_root/'complete.json')})
    add({str(chain_root/name):digest for name,digest in doc['files'].items()})
    root = Path(__file__).resolve().parents[2]
    add({str(root/name):sha(root/name) for name in (
        'nn_meta/v7/entry_demand.py','nn_meta/v7/chain.py','nn_meta/v7/quotes.py',
        'scripts/build_v7_entry_demand.py')})
    return result


def build_entry_demand(path, stores, chain_root, *, reserve_bytes,
                       max_quote_age_ns=30_000_000_000, expected_timeframes=(1,5,15,30)):
    """Collapse repeated variant decisions on disk, preserving their full census."""
    from nn_meta.v7.chain import ObservedChain
    from nn_meta.v7.provenance import runtime_manifest
    stores = sorted(stores, key=lambda s:s.features.declaration['minutes'])
    if (not stores or [s.features.declaration['minutes'] for s in stores]!=list(expected_timeframes)
            or type(max_quote_age_ns) is not int or not 0 < max_quote_age_ns <= 60_000_000_000):
        raise ValueError('Exact distinct timeframe stores and bounded quote seed age required')
    first = stores[0]
    for store in stores:
        if (store.declaration['entry_eligibility'] is None
                or any(store.features.declaration[k]!=first.features.declaration[k]
                       for k in ('security_id','raw_identity','calendar'))
                or any(store.declaration[k]!=first.declaration[k]
                       for k in ('start','end','symbols_by_date','simulator_policy','entry_eligibility'))):
            raise ValueError('Same security, raw history, dates, policy and dated entry eligibility required')
    path, chain_root = Path(path), Path(chain_root)
    inputs = _parents(stores, chain_root)
    declaration = dict(schema=FORMAT, inputs=inputs, runtime=runtime_manifest(),
        security_id=first.declaration['security_id'], start=first.declaration['start'],
        end=first.declaration['end'], timeframes=list(expected_timeframes), targets=list(TARGETS),
        proposal_stores=[str(s.path.resolve()) for s in stores],
        chain=str((chain_root/'contracts.parquet').resolve()),
        max_quote_age_ns=max_quote_age_ns, scope='selected-contract pre-decision feature windows only',
        execution_coverage=False, research_ready=False)
    fingerprint = identity(declaration)
    if path.exists():
        verify(path,expected_identity=fingerprint)
        return json.loads((path/'report.json').read_text())
    path.parent.mkdir(parents=True,exist_ok=True)
    _disk(path.parent,reserve_bytes)
    raw = pd.read_parquet(first.features.path/'basis/raw.parquet')
    available = pd.DatetimeIndex(raw.available_at)
    if available.has_duplicates or not available.is_monotonic_increasing:
        raise ValueError('Unique ordered causal raw-price availability required')
    calendar = {s['date']:s for s in first.features.declaration['calendar']['sessions']}
    with transaction(path) as temp:
        db = sqlite3.connect(temp/'demand.sqlite3')
        try:
            db.executescript('''
                PRAGMA temp_store=FILE;
                PRAGMA cache_size=-8192;
                CREATE TABLE decisions(symbol TEXT, decision_ns INTEGER, right TEXT, minutes INTEGER,
                    proposals INTEGER NOT NULL, PRIMARY KEY(symbol,decision_ns,right,minutes)) WITHOUT ROWID;
                CREATE TABLE selections(selection_id TEXT PRIMARY KEY, symbol TEXT, decision_ns INTEGER,
                    right TEXT, target_dte INTEGER, status TEXT, contract TEXT, raw_spot REAL,
                    raw_available_ns INTEGER, first_seen TEXT, expiry TEXT) WITHOUT ROWID;
                CREATE TABLE requests(request_id TEXT PRIMARY KEY, contract TEXT, kind TEXT,
                    start_ns INTEGER, end_ns INTEGER, date TEXT) WITHOUT ROWID;
                CREATE INDEX request_groups ON requests(contract,date,kind,start_ns,end_ns);
                CREATE TABLE feature_links(selection_id TEXT, minutes INTEGER, request_id TEXT,
                    PRIMARY KEY(selection_id,minutes,request_id)) WITHOUT ROWID;
            ''')
            total = 0
            for store in stores:
                pending = []
                for row in store.rows(batch_size=4096):
                    pending.append((row['symbol'],row['decision_ns'],row['right'],row['signal_minutes'],1))
                    total += 1
                    if len(pending)==4096:
                        db.executemany('INSERT INTO decisions VALUES(?,?,?,?,?) ON CONFLICT DO UPDATE SET proposals=proposals+1',pending)
                        db.commit(); pending.clear()
                if pending:
                    db.executemany('INSERT INTO decisions VALUES(?,?,?,?,?) ON CONFLICT DO UPDATE SET proposals=proposals+1',pending)
                    db.commit()
            if total!=sum(s.report['proposals'] for s in stores):
                raise ValueError('Entry-demand census differs from admitted proposals')
            chains = {}
            decisions = db.execute('SELECT symbol,decision_ns,right FROM decisions GROUP BY symbol,decision_ns,right ORDER BY symbol,decision_ns,right')
            for number,(symbol,clock,right) in enumerate(decisions):
                stamp = pd.Timestamp(clock,unit='ns',tz='UTC')
                day = stamp.tz_convert('America/New_York').date().isoformat()
                if day not in calendar:raise ValueError('Proposal lies outside captured sessions')
                opening = pd.Timestamp(day+' '+calendar[day]['open'],tz='America/New_York').value
                closing = pd.Timestamp(day+' '+calendar[day]['close'],tz='America/New_York').value
                if not opening < clock <= closing:raise ValueError('Feature decision is outside its stock session')
                position = available.searchsorted(stamp,side='right')-1
                fresh = position >= 0 and 0 <= clock-available[position].value <= 60_000_000_000
                spot = float(raw.Close.iloc[position]) if fresh else None
                raw_clock = int(available[position].value) if fresh else None
                if symbol not in chains:
                    # A security may have dated ticker aliases. Retain one root
                    # at a time instead of every root's catalogue in memory.
                    chains.clear(); chains[symbol] = ObservedChain(chain_root/'contracts.parquet',symbol)
                minutes = [r[0] for r in db.execute('SELECT minutes FROM decisions WHERE symbol=? AND decision_ns=? AND right=?',
                                                   (symbol,clock,right))]
                for target in TARGETS:
                    sid = selection_id(symbol,clock,right,target)
                    chosen = chains[symbol].select(stamp.tz_convert('America/New_York').date(),spot,right,target) if fresh else None
                    status = 'no_fresh_raw_spot' if not fresh else ('selected' if chosen else 'no_contract')
                    contract = chosen['ticker'].removeprefix('O:') if chosen else None
                    db.execute('INSERT INTO selections VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                        (sid,symbol,clock,right,target,status,contract,spot,raw_clock,
                         chosen['first_seen'].isoformat() if chosen else None,chosen['expiry'].isoformat() if chosen else None))
                    if not chosen:continue
                    for minute in minutes:
                        start = clock-minute*60_000_000_000
                        if start < opening:raise ValueError('Feature window crosses its declared session opening')
                        prefix = max(opening,start-max_quote_age_ns)
                        for kind in ('quotes','trades'):
                            scope = dict(contract=contract,kind=kind,start_ns=prefix,end_ns=clock)
                            rid = identity(scope)
                            db.execute('INSERT OR IGNORE INTO requests VALUES(?,?,?,?,?,?)',
                                (rid,contract,kind,prefix,clock,day))
                            db.execute('INSERT INTO feature_links VALUES(?,?,?)',(sid,minute,rid))
                if number % 1024 == 1023:
                    db.commit(); _disk(temp,reserve_bytes)
            report = dict(proposals=total, variants=sum(s.report['variants'] for s in stores),
                distinct_feature_decisions=db.execute('SELECT COUNT(*) FROM decisions').fetchone()[0],
                distinct_selection_decisions=db.execute('SELECT COUNT(*) FROM (SELECT DISTINCT symbol,decision_ns,right FROM decisions)').fetchone()[0],
                selection_statuses=dict(db.execute('SELECT status,COUNT(*) FROM selections GROUP BY status')),
                requests=db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],
                feature_links=db.execute('SELECT COUNT(*) FROM feature_links').fetchone()[0],
                contracts=db.execute('SELECT COUNT(DISTINCT contract) FROM requests').fetchone()[0],
                research_ready=False, execution_coverage=False,
                outstanding=['entry/exit execution windows and minute marks','roll and physical delivery demand',
                             'dated option class hours and standard deliverables','full captured tick coverage'])
            db.commit()
        finally:
            db.close()
        if any(sha(p)!=h for p,h in inputs.items()):raise ValueError('Entry-demand inputs changed during build')
        _write(temp/'declaration.json',declaration); _write(temp/'report.json',report)
        receipt(temp,dict(identity=fingerprint,research_ready=False))
    return report


class EntryDemand:
    def __init__(self,path):
        self.path = Path(path)
        document = verify(self.path)
        self.declaration = json.loads((self.path/'declaration.json').read_text())
        self.report = json.loads((self.path/'report.json').read_text())
        if self.declaration['schema']!=FORMAT or document['identity']!=identity(self.declaration):
            raise ValueError('Entry demand declaration differs')
        self.verify_bindings()

    def verify_bindings(self):
        from nn_meta.v7.provenance import runtime_manifest
        if (any(sha(p)!=h for p,h in self.declaration['inputs'].items())
                or identity(runtime_manifest())!=identity(self.declaration['runtime'])):
            raise ValueError('Entry demand sources, inputs or runtime changed')

    def connection(self):
        return sqlite3.connect(f'file:{self.path}/demand.sqlite3?mode=ro',uri=True)

    def lookup(self,proposal,*,target_dte):
        if type(target_dte) is not int or target_dte not in TARGETS or proposal['security_id']!=self.declaration['security_id']:
            raise ValueError('Unknown target or foreign security')
        with self.connection() as db:
            db.row_factory = sqlite3.Row
            key = selection_id(proposal['symbol'],proposal['decision_ns'],proposal['right'],target_dte)
            row = db.execute('SELECT * FROM selections WHERE selection_id=?',(key,)).fetchone()
            decision = db.execute('SELECT proposals FROM decisions WHERE symbol=? AND decision_ns=? AND right=? AND minutes=?',
                (proposal['symbol'],proposal['decision_ns'],proposal['right'],proposal['signal_minutes'])).fetchone()
            if row is None or decision is None:raise ValueError('Proposal decision is absent from entry demand')
            links = db.execute('SELECT request_id FROM feature_links WHERE selection_id=? AND minutes=? ORDER BY request_id',
                               (key,proposal['signal_minutes'])).fetchall()
            return dict(row)|dict(request_ids=[r[0] for r in links])

    def request_batches(self,*,maximum=10000):
        """Keep each contract/day together so separate capture batches cannot overlap."""
        if type(maximum) is not int or not 1 <= maximum <= 10000:
            raise ValueError('Capture batches require 1–10000 requests')
        self.verify_bindings()
        with self.connection() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute('SELECT * FROM requests ORDER BY contract,date,kind,start_ns,end_ns')
            batch = []
            for _, group in groupby(rows,key=lambda r:(r['contract'],r['date'])):
                part = []
                for row in group:
                    part.append({k:row[k] for k in ('request_id','contract','kind','start_ns','end_ns')})
                    if len(part)>maximum:raise ValueError('One contract/day exceeds the bounded capture batch')
                if len(batch)+len(part)>maximum:
                    yield batch; batch=[]
                batch.extend(part)
            if batch:yield batch

    def export_requests(self,path,*,maximum=10000):
        """Produce immutable bounded inputs for the existing shared-quota capturer."""
        path = Path(path)
        binding = dict(parent=str(self.path.resolve()),parent_sha256=sha(self.path/'complete.json'),
                       maximum=maximum,scope=self.declaration['scope'])
        self.verify_bindings()
        if path.exists():
            verify(path,expected_identity=identity(binding))
            return json.loads((path/'report.json').read_text())
        with transaction(path) as temp:
            batches=[]
            for number,rows in enumerate(self.request_batches(maximum=maximum)):
                name=f'requests-{number:05d}.json'
                _write(temp/name,rows)
                batches.append(dict(path=name,requests=len(rows),sha256=sha(temp/name)))
            if sum(b['requests'] for b in batches)!=self.report['requests']:
                raise ValueError('Capture export omitted feature requests')
            self.verify_bindings()
            report=dict(batches=batches,requests=self.report['requests'],execution_coverage=False)
            _write(temp/'binding.json',binding);_write(temp/'report.json',report)
            receipt(temp,dict(identity=identity(binding),research_ready=False))
        return report
