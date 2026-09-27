"""Receipt-backed adapters for the versioned V7 shared execution runner."""
import json
from pathlib import Path

from nn_meta.v7.execution import CaptureUnavailable, fill_clock
from nn_meta.v7.physical import PhysicalPolicy
from nn_meta.v7.quote_archive import QuoteArchive
from nn_meta.v7.storage import identity, sha, verify


class BoundInputs:
    def __init__(self):
        self.inputs = {}

    def file(self, path):
        path = Path(path).resolve()
        digest = sha(path)
        if str(path) in self.inputs and self.inputs[str(path)] != digest:
            raise ValueError('Input changed during integrated execution')
        self.inputs[str(path)] = digest
        return path

    def store(self, path):
        path = Path(path).resolve()
        header = verify(path)
        self.file(path / 'complete.json')
        for name, digest in header['files'].items():
            self.file(path / name)
            if self.inputs[str(path / name)] != digest:
                raise ValueError('Receipt changed during integration')
        return header

    def check(self):
        if any(sha(p) != h for p, h in self.inputs.items()):
            raise ValueError('Integrated execution inputs changed')


class RecordingOptions(QuoteArchive):
    """Use the current packed reader; report only uncovered requested intervals."""
    def __init__(self, parent):
        self.parent, self.policy = parent, parent.policy
        self.pending = []

    def window(self, contract, kind, start_ns, end_ns):
        try:
            return self.parent.window(contract, kind, start_ns, end_ns)
        except CaptureUnavailable:
            cursor = start_ns
            for lo, hi in self.parent.db.execute(
                    'SELECT start_ns,end_ns FROM ranges WHERE contract=? AND kind=? '
                    'AND start_ns<? AND end_ns>? ORDER BY start_ns',
                    (contract.removeprefix('O:'), kind, end_ns, start_ns)):
                if lo > cursor:
                    self._missing(contract, kind, cursor, min(lo, end_ns))
                cursor = max(cursor, min(hi, end_ns))
            if cursor < end_ns:
                self._missing(contract, kind, cursor, end_ns)
            raise

    def _missing(self, contract, kind, start, end):
        request = dict(provider='massive', kind=kind, contract=contract.removeprefix('O:'),
                       start_ns=int(start), end_ns=int(end), purpose='shared_portfolio_mark')
        self.pending.append(dict(request, request_id=identity(request)))


class RecordingStocks:
    def __init__(self, parent):
        self.parent, self.policy, self.pending = parent, parent.policy, []

    def _read(self, symbol, start, end, purpose, call):
        try:
            return call()
        except CaptureUnavailable:
            request = dict(provider='alpaca', kind='stock_quotes', symbol=symbol,
                           start_ns=int(start), end_ns=int(end), purpose=purpose)
            self.pending.append(dict(request, request_id=identity(request)))
            raise

    def mark(self, symbol, clock):
        return self._read(symbol, max(0, clock-self.policy.max_mark_age_ns), clock+1,
                          'funded_stock_mark', lambda: self.parent.mark(symbol, clock))

    def first_fill(self, symbol, clock, *, side, quantity):
        return self._read(symbol, clock+self.policy.latency_ns,
                          clock+self.policy.entry_deadline_ns+1, 'funded_stock_liquidation',
                          lambda: self.parent.first_fill(symbol, clock, side=side, quantity=quantity))


class PhysicalInputs:
    """Connect captured schedules/quotes and exact official-expiry evidence.

    Missing official evidence is requested only for an actually held expiry.
    No closing aggregate or intrinsic-value option sale is substituted.
    """
    def __init__(self, *, settlement_calendar, stock_archive, hours, references,
                 expiry_root, bindings, cash_entitlements=(), renames=(), splits=()):
        self.settlement_calendar, self.stock_archive = settlement_calendar, stock_archive
        self.hours, self.references = hours, references
        self.expiry_root = Path(expiry_root) if expiry_root is not None else None
        self.bindings, self.pending = bindings, []
        self.policy = PhysicalPolicy()
        self.cash_entitlements, self.renames, self.splits = cash_entitlements, renames, splits

    def expiry_check_clock(self, contract):
        return self.hours.cutoff(contract) + 15*60_000_000_000

    def expiry_evidence(self, contract):
        from options.data.provider import parse_occ_symbol
        day = parse_occ_symbol(contract)[1].isoformat()
        request = dict(provider='official_expiry', kind='exercise_reference',
                       contract=contract, date=day)
        directory = self.expiry_root / contract / day if self.expiry_root else None
        if directory is None or not (directory / 'complete.json').exists():
            self.pending.append(dict(request, request_id=identity(request)))
            raise CaptureUnavailable('Exact official expiration evidence is not captured')
        self.bindings.store(directory)
        document = json.loads((directory / 'reference.json').read_text())
        if document.get('schema') != 'v7-official-expiry-reference-v1' or not document.get('inputs'):
            raise ValueError('Bound official expiry reference required')
        for path, digest in document['inputs'].items():
            if sha(self.bindings.file(path)) != digest:
                raise ValueError('Official expiry source changed')
        try:
            metadata = dict(self.references.standard(contract, day))
        except (FileNotFoundError, CaptureUnavailable):
            request = dict(provider='massive', kind='contract_reference', contract=contract, date=day)
            self.pending.append(dict(request, request_id=identity(request)))
            raise CaptureUnavailable('Expiry deliverable reference missing') from None
        return dict(metadata=metadata, reference=document['reference'])


def candidates_from_discovery(document):
    """Keep every source path, including incomplete and unfilled candidates."""
    result = []
    for case in document['cases']:
        proposal, path = case['source_proposal'], case['replay']
        candidate = dict(proposal, security_id=case['security_id'], path=path,
                         score=0., score_available_ns=proposal['decision_ns'])
        pending = case['pending']
        if case.get('blackout') or path.get('blackout'):
            # A retrospective exclusion cannot silently rerank a shared portfolio.
            raise ValueError('Blackout path requires an explicit shared-portfolio exclusion treatment')
        if pending:
            clocks = [r['clock_ns'] for r in path['marks'] if r['status'] == 'uncaptured']
            clocks += [r['clock_ns'] for r in path['attempts'] if r['status'] == 'uncaptured']
            if not clocks:
                raise ValueError('Pending input has no recorded first missing clock')
            candidate.update(pending_at_ns=min(clocks), pending_requests=pending)
        if path['label_complete'] and (pending or path['open_positions']):
            raise ValueError('Completed path retains a gap or position')
        if path['fills'] and fill_clock(path['fills'][0]) < proposal['decision_ns']:
            raise ValueError('Path precedes its source proposal')
        result.append(candidate)
    return result
