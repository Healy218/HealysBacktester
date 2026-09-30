import json
from pathlib import Path
import sqlite3

import pytest

from nn_meta.v7.storage import receipt
from scripts.reconcile_v7_frontier_v2 import reconcile
from scripts.finish_v7_required_inputs import terminal, terminal_or_running


def seal(path, files):
    path.mkdir(parents=True)
    for name, value in files.items():
        (path / name).write_text(json.dumps(value))
    return path


def inputs(tmp_path):
    contract = 'SPY220318C00420000'
    quote = dict(provider='massive', kind='quotes', contract=contract,
                 start_ns=100, end_ns=300, request_id='quote')
    ref = dict(provider='massive', kind='contract_reference', contract=contract,
               date='2022-03-15', request_id='ref')
    stock = dict(provider='alpaca', kind='stock_quotes', symbol='SPY',
                 start_ns=100, end_ns=300, request_id='stock')
    raw = seal(tmp_path / 'raw', {'requests.json': {'quote': quote, 'ref': ref, 'stock': stock},
        'security-requests.json': [['sid', 'quote'], ['sid', 'ref'], ['sid', 'stock']],
        'capture-plan.json': {'captures': [quote]}})
    receipt(raw, {})
    quotes = seal(tmp_path / 'quotes', {})
    with sqlite3.connect(quotes / 'index.sqlite3') as db:
        db.execute('CREATE TABLE ranges(contract,kind,start_ns,end_ns)')
        db.executemany('INSERT INTO ranges VALUES (?,?,?,?)',
                       [(contract, 'quotes', 100, 150), (contract, 'quotes', 200, 250)])
    receipt(quotes, {})
    refs = seal(tmp_path / 'refs', {})
    with sqlite3.connect(refs / 'coverage.sqlite3') as db:
        db.execute('CREATE TABLE observed(security_id,contract,date,admission,pack,receipt_sha256)')
        db.execute('INSERT INTO observed VALUES (?,?,?,?,?,?)',
                   ('sid', contract, '2022-03-15', 'approved_blackout', 'retained', 'anchor'))
    receipt(refs, {})
    return raw, quotes, refs


def test_new_epoch_subtracts_coverage_preserves_reuse_and_unsupported_requests(tmp_path):
    raw, quotes, refs = inputs(tmp_path)
    output = tmp_path / 'output'
    report = reconcile(raw, quotes, refs, output)
    captures = json.loads((output / 'capture-plan.json').read_text())['captures']
    assert [(r['start_ns'], r['end_ns']) for r in captures] == [(150, 200), (250, 300)]
    assert report['reused_reference_links'] == 1
    assert report['reference_requests'] == 0
    assert report['unsupported_requests'] == 1
    assert report['original_pending_rows'] == 3 and report['pending_rows'] == 2
    assert json.loads((output / 'reused-references.json').read_text())[0]['admission'] == 'approved_blackout'
    assert json.loads((output / 'unsupported-requests.json').read_text())[0]['provider'] == 'alpaca'
    assert reconcile(raw, quotes, refs, output) == report
    # A valid new epoch cannot silently reuse a receipt built against older coverage.
    with sqlite3.connect(quotes / 'index.sqlite3') as db:
        db.execute('INSERT INTO ranges VALUES (?,?,?,?)', ('SPY220318C00420000', 'quotes', 150, 200))
    (quotes / 'complete.json').unlink()
    receipt(quotes, {})
    with pytest.raises(ValueError, match='identity mismatch'):
        reconcile(raw, quotes, refs, output)


def test_reference_reuse_is_security_specific(tmp_path):
    raw, quotes, refs = inputs(tmp_path)
    with sqlite3.connect(refs / 'coverage.sqlite3') as db:
        db.execute('UPDATE observed SET security_id="other"')
    (refs / 'complete.json').unlink()
    receipt(refs, {})
    report = reconcile(raw, quotes, refs, tmp_path / 'output')
    assert report['reference_requests'] == 1
    assert report['reused_reference_links'] == 0


@pytest.mark.parametrize('mode,status,done,required', [
    ('capture', 'captured_snapshot', 'capture_windows_complete', 'capture_windows_required'),
    ('discovery', 'discovered', 'securities_discovered', 'securities_required'),
    ('replay', 'replayed_pending', 'securities_replayed', 'securities_required'),
])
def test_only_reconciled_terminal_receipts_complete(mode, status, done, required):
    assert terminal({'status': status, done: 10, required: 10}, mode)
    assert not terminal({'status': 'checkpointed', done: 3, required: 10}, mode)
    with pytest.raises(ValueError, match='completion count'):
        terminal({'status': status, done: 9, required: 10}, mode)
    with pytest.raises(RuntimeError):
        terminal({'status': status, done: 10, required: 10, 'error': 'provider failed'}, mode)
    with pytest.raises(ValueError, match='stopped'):
        terminal({'status': 'running', done: 10, required: 10}, mode)


def test_concurrent_discovery_waits_but_never_hides_failure():
    assert not terminal_or_running({'status': 'running', 'failed_securities': {}}, 'discovery')
    assert not terminal_or_running({'status': 'checkpointed'}, 'discovery')
    with pytest.raises(RuntimeError):
        terminal_or_running({'status': 'running', 'failed_securities': {'sid': 1}}, 'discovery')


def test_initial_subset_cannot_publish_full_scope_candidate(tmp_path, monkeypatch):
    import scripts.finish_v7_required_inputs as m
    v = tmp_path / 'validation'
    v.mkdir()
    monkeypatch.setattr(m, 'V', v)
    monkeypatch.setattr(m, 'STATE', v / 'supervisor')
    monkeypatch.setattr(m, 'RECOVERY', v / 'recovery')
    monkeypatch.setattr(m, 'ORIGINAL', v / 'original')
    seal(m.RECOVERY, {'progress.json': {'status': 'discovered', 'securities_discovered': 591, 'securities_required': 591}})
    seal(v / 'v7-mrha-payload-migration-20260929-r1', {'progress.json': {'status': 'complete', 'files_moved': 5, 'files_required': 5}})
    refs = seal(v / 'v7-reference-epoch-20260930-r0', {'report.json': {}})
    receipt(refs, {})
    c = object.__new__(m.Controller)
    c.check = lambda: None
    c.capture = lambda *a, **kw: v / 'quotes'
    c.replay = lambda *a: v / 'initial-replay'
    seen, reports = [], []
    def epoch(parent, quotes, references, number, scope):
        seen.append((parent, scope))
        return None, quotes, references
    c.epoch = epoch
    c.report = lambda phase, **kw: reports.append(phase)
    c.frontier()
    assert seen == [(v / 'initial-replay', 'initial_93'), (m.ORIGINAL, 'full_591')]
    assert reports == ['closure_candidate_ready']
