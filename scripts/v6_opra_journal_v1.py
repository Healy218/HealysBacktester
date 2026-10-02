"""Direct-WebSocket receipt semantics over the existing append-only journal."""
from datetime import datetime, timezone
from nn_meta.live.feeds.tick_journal import (
    TickJournal, TickJournalError, canonical_contract, normalize_message, _ns,
)

RECEIPT_BASIS='websocket_handler_after_msgpack_decode'


class V6OpraJournal(TickJournal):
    def record(self, raw, *, received_at_ns, received_monotonic_ns=None):
        received=_ns(received_at_ns)
        day=datetime.fromtimestamp(received//1_000_000_000,timezone.utc).date().isoformat()
        if day!=self._day:self.set_contracts(self._desired,received_at_ns=received)
        if self._lock is None:raise TickJournalError('journal is closed')
        if not isinstance(raw,dict):raise TickJournalError('expected raw WebSocket message')
        contract=canonical_contract(raw.get('S'))
        if contract not in self._desired or contract not in self._admitted:
            self.skipped_contract_ticks+=1
            return False
        record=normalize_message(raw,received_at_ns=received)
        record.update(receipt_basis=RECEIPT_BASIS,capture_id=self.capture_id,journal_sequence=self.sequence)
        if received_monotonic_ns is not None:record['received_monotonic_ns']=_ns(received_monotonic_ns)
        self._append(self._open(record['kind']),record)
        self.sequence+=1;self.rows[record['kind']]+=1
        self.normalization_errors+=int('normalization_error' in record)
        self.last_received_at_ns=received;self.last_event_timestamp_ns=record['event_timestamp_ns']
        return True

    def status(self):
        return dict(super().status(),receipt_basis=RECEIPT_BASIS)
