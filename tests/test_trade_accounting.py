import json
from decimal import Decimal

import pytest
from tests.test_taken_trades import queued, message, rows, OCC
from nn_meta.live.taken_trades import handle
from nn_meta.live.trade_accounting import summary, reconcile


def setup(tmp_path):
    q, ident = queued(tmp_path)
    handle(q, message(f'/taken {ident} 3 @ 1.00'), '123')
    return q, ident


def command(q, text, uid):
    return handle(q, message(text, uid), '123')


def test_partial_final_sale_exact_cash_flows_and_fees(tmp_path):
    q, ident = setup(tmp_path)
    command(q, f'/entryfees {ident} .09', 2)
    result = command(q, f'/sold {ident} 1 @ 1.20 fees .04 ref fill-1', 3)
    assert '$19.93' in result and 'remaining by fills: 2' in result
    assert rows(q)[0]['status'] == 'open'
    assert '2 @ $1.00' in command(q, '/selllist', 4)
    result = command(q, f'/sold {ident} 2 @ .80 fees .08 ref fill-2', 5)
    assert '$-20.21' in result and rows(q)[0]['status'] == 'closed'
    with q.connect() as db:
        a = summary(db, rows(q)[0])
        assert a['net'] == Decimal('-20.21') and a['remaining'] == 0


def test_unknown_fees_not_zero_and_can_complete_after_close(tmp_path):
    q, ident = setup(tmp_path)
    result = command(q, f'/sold {ident} 3 @ 0', 2)
    assert 'net P/L: unknown' in result and 'gross P/L: $-300.00' in result
    command(q, f'/entryfees {ident} 0', 3)
    result = command(q, f'/salefees {ident} 2 0 ref expiration-record', 4)
    assert 'net P/L: $-300.00' in result
    assert 'expiration-record' in command(q, f'/trade {ident}', 5)


def test_same_update_and_broker_reference_idempotent(tmp_path):
    q, ident = setup(tmp_path)
    text = f'/sold {ident} 1 @ 2 fees 0 ref unique'
    first = command(q, text, 2)
    assert first == command(q, text, 2)
    assert 'already recorded' in command(q, text, 3)
    assert 'different fill details' in command(q, text.replace('@ 2', '@ 3'), 4)
    with q.connect() as db:
        assert summary(db, rows(q)[0])['sold'] == 1


@pytest.mark.parametrize('fill', ['4 @ 1', '0 @ 1', '1 @ -1', '1 @ nan', '1 @ inf', '1 @ 1 fees -1', '1 @ 1 fees ..', '1 @ 1 junk', '1 @ 1000000001'])
def test_invalid_sales_leave_position_unchanged(tmp_path, fill):
    q, ident = setup(tmp_path)
    command(q, f'/sold {ident} {fill}', 2)
    with q.connect() as db:
        assert not summary(db, rows(q)[0])['sales']
    assert rows(q)[0]['status'] == 'open'


def test_legacy_close_can_backfill_sales_without_inventing_fills(tmp_path):
    q, ident = setup(tmp_path)
    assert 'incomplete' in command(q, f'/sold {ident}', 2)
    assert 'accounting is incomplete' in command(q, f'/trade {ident}', 3)
    command(q, f'/sold {ident} 1 @ 2', 4)
    assert rows(q)[0]['status'] == 'closed'
    command(q, f'/sold {ident} 2 @ 1', 5)
    assert 'accounting is incomplete' not in command(q, f'/trade {ident}', 6)


def test_entry_cannot_change_after_sales(tmp_path):
    q, ident = setup(tmp_path)
    command(q, f'/sold {ident} 1 @ 2', 2)
    assert 'locked' in command(q, f'/taken {ident} 4 @ 3', 3)
    assert rows(q)[0]['quantity'] == 3 and rows(q)[0]['fill_price'] == 1


def test_exit_due_survives_partial_sale(tmp_path):
    q, ident = setup(tmp_path)
    with q.connect() as db:
        db.execute("UPDATE taken_trades SET status='exit_due',exit_notice='exit',notice_sent=1")
    command(q, f'/sold {ident} 1 @ 2', 2)
    assert rows(q)[0]['status'] == 'exit_due' and rows(q)[0]['notice_sent'] == 1


def test_reconciliation_match_missing_and_mismatched_records(tmp_path):
    q, ident = setup(tmp_path)
    command(q, f'/entryfees {ident} .09', 2)
    command(q, f'/sold {ident} 1 @ 1.20 fees .04 ref f1', 3)
    record = dict(trade_id=ident, contract=OCC, entry_quantity=3, entry_price='1', entry_fees='.09', remaining_quantity=2,
                  sales=[dict(quantity=1, premium='1.2', fees='.04', broker_ref='f1')])
    with q.connect() as db:
        before = db.total_changes
        assert reconcile(db, [record])[0]['matched']
        assert not reconcile(db, [dict(record, remaining_quantity=0)])[0]['matched']
        assert not reconcile(db, [dict(record, entry_fees=None)])[0]['matched']
        assert not reconcile(db, [dict(record, sales=[])])[0]['matched']
        with pytest.raises(ValueError, match='Duplicate'):
            reconcile(db, [record, record])
        assert db.total_changes == before


def test_migration_preserves_old_positions(tmp_path):
    from nn_meta.live.alert_batches import Batches
    q, ident = setup(tmp_path)
    with q.connect() as db:
        db.execute('DROP TABLE taken_sales')
        db.execute('ALTER TABLE taken_trades DROP COLUMN actual_entry_fees')
    Batches(q.path)
    Batches(q.path)
    assert rows(q)[0]['quantity'] == 3
    assert 'remaining by fills: 3' in command(q, f'/trade {ident}', 2)


def test_cli_readonly_match(tmp_path):
    import subprocess
    import sys
    q, ident = setup(tmp_path)
    command(q, f'/entryfees {ident} 0', 2)
    broker = tmp_path/'broker.json'
    broker.write_text(json.dumps([dict(trade_id=ident, contract=OCC, entry_quantity=3, entry_price=1,
                                     entry_fees=0, remaining_quantity=3, sales=[])]))
    before = q.path.read_bytes()
    result = subprocess.run([sys.executable, 'scripts/reconcile_taken.py', '--database', str(q.path), '--broker-json', str(broker)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)[0]['matched']
    assert q.path.read_bytes() == before


def test_missing_entry_price_can_be_added_after_closing(tmp_path):
    q, ident = queued(tmp_path)
    command(q, f'/taken {ident} 3', 1)
    assert 'unknown entry premium' in command(q, f'/sold {ident} 3 @ .50 fees 0', 2)
    command(q, f'/entryfees {ident} 0', 3)
    assert 'net P/L: $-150.00' in command(q, f'/entryprice {ident} 1', 4)
    assert 'previously unrecorded' in command(q, f'/entryprice {ident} 2', 5)


def test_fee_edits_keep_audit_history(tmp_path):
    q, ident = setup(tmp_path)
    command(q, f'/entryfees {ident} .09', 2)
    command(q, f'/entryfees {ident} .10', 3)
    command(q, f'/entryfees {ident} .10', 3)
    with q.connect() as db:
        events = db.execute("SELECT arguments FROM taken_accounting_events WHERE action='entryfees' ORDER BY update_id").fetchall()
    assert [json.loads(e[0]) for e in events] == [['.09'], ['.10']]


def test_two_concurrent_sales_cannot_oversell(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    q, ident = setup(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda uid: command(q, f'/sold {ident} 2 @ 1', uid), [2, 3]))
    assert sum('Sale recorded' in r for r in results) == 1
    with q.connect() as db:
        assert summary(db, rows(q)[0])['remaining'] == 1


def test_sale_reference_cannot_be_reassigned_and_large_id_rejected(tmp_path):
    q, ident = setup(tmp_path)
    command(q, f'/sold {ident} 1 @ 1 ref original', 2)
    assert 'cannot be reassigned' in command(q, f'/salefees {ident} 2 0 ref replacement', 3)
    assert 'out of range' in command(q, f'/salefees {ident} 999999999999999999999 0', 4)
    assert 'original' in command(q, f'/trade {ident}', 5)
