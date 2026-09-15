"""Observed-quote label replay with explicit rolls, failed fills and censoring.

Individual proposal labels use one unit of allocated capital. A separate
portfolio must allocate the shared five slots; these returns are not summed
as independently funded positions.
"""
import pandas as pd

from nn_meta.v7.execution import CashLedger, QuotePolicy, QuoteUnavailable, CaptureUnavailable


def replay(proposal, clocks, archive, references, *, select_contract, expiry_cutoff,
           session_close, policy=QuotePolicy(), max_rolls=60):
    if type(max_rolls) is not int or max_rolls < 0:
        raise ValueError('Explicit nonnegative roll limit required')
    clocks = list(clocks)
    if any(type(t) is not int for t in clocks) or clocks != sorted(set(clocks)):
        raise ValueError('Ordered unique minute clocks required')
    entry = proposal['decision_ns']
    exit_at = proposal.get('exit_decision_ns')
    if type(entry) is not int or (exit_at is not None and (type(exit_at) is not int or exit_at <= entry)):
        raise ValueError('Proposal requires a positive holding horizon')
    if not clocks or entry not in clocks:
        raise ValueError('Replay clocks must include the entry decision')
    ledger = CashLedger(capital=10000., slots=1, fraction=1., policy=policy)
    marks, attempts = [], []
    rolls, started, pending, terminal = 0, False, False, False
    capture_complete = True
    reason = 'censored'
    terminal_clock = None

    def observed_mark(clock):
        nonlocal capture_complete
        if not ledger.positions:
            return
        position = next(iter(ledger.positions.values()))
        try:
            # Session capture is [open, close). The closing valuation uses
            # the final observation strictly before that regular close.
            quote_clock = min(clock, session_close(clock) - 1)
            value = archive.mark(position['contract'], quote_clock)
            equity = ledger.cash + position['quantity'] * policy.multiplier * value['bid']
            marks.append({'clock_ns': clock, 'contract': position['contract'], 'status': 'observed',
                          'quote_as_of_ns': quote_clock, 'equity': equity, **value})
        except CaptureUnavailable as exc:
            capture_complete = False
            marks.append({'clock_ns': clock, 'status': 'uncaptured', 'reason': str(exc)})
        except QuoteUnavailable as exc:
            # A complete but stale/invalid market is an explicit valuation
            # gap. Shared-portfolio allocation must wait for fresh equity.
            marks.append({'clock_ns': clock, 'status': 'unavailable', 'reason': str(exc)})

    def buy(clock, *, is_roll):
        contract = select_contract(clock)
        if contract is None:
            attempts.append({'clock_ns': clock, 'action': 'roll_buy' if is_roll else 'entry', 'status': 'no_contract'})
            return False
        day = pd.Timestamp(clock, unit='ns', tz='UTC').tz_convert('America/New_York').date()
        metadata = references.standard(contract, day.isoformat())
        if metadata['underlying'] != proposal['symbol'].replace('.', '') or metadata['right'] != proposal['right']:
            raise ValueError('Selected contract does not match proposal identity/direction')
        if clock >= expiry_cutoff(contract):
            attempts.append({'clock_ns': clock, 'contract': contract, 'status': 'past_liquidation_cutoff'})
            return False
        close = session_close(clock)
        if clock + policy.latency_ns >= close:
            return False
        fill = archive.first_fill(contract, clock, side='buy',
                                  deadline_ns=min(clock + policy.entry_deadline_ns, close - 1))
        attempts.append({'clock_ns': clock, 'contract': contract, 'action': 'roll_buy' if is_roll else 'entry',
                         'status': 'filled' if fill else 'observed_unfilled',
                         'metadata_receipt_sha256': metadata['metadata_receipt_sha256']})
        if fill is None:
            return False
        accepted = ledger.buy('position', proposal['symbol'], fill, equity=ledger.cash,
                              decision_date=day, budget=ledger.cash, roll_of=rolls if is_roll else None)
        if not accepted:
            raise ValueError('Single-proposal ledger unexpectedly rejected an observed fill')
        observed_mark(fill['sip_timestamp'])
        return True

    for clock in clocks:
        if clock < entry or clock < ledger.last_clock:
            continue
        try:
            if not started:
                if clock != entry:
                    break
                started = buy(clock, is_roll=False)
                if not started:
                    reason = 'observed_unfilled_entry'
                    break
                continue
            if pending:
                if exit_at is not None and clock >= exit_at:
                    terminal, reason = True, 'signal_exit_while_roll_unfilled'
                    terminal_clock = clock
                    break
                pending = not buy(clock, is_roll=True)
                continue
            position = ledger.positions['position']
            contract = position['contract']
            cutoff = expiry_cutoff(contract)
            day = pd.Timestamp(clock, unit='ns', tz='UTC').tz_convert('America/New_York').date().isoformat()
            from options.data.provider import parse_occ_symbol
            if parse_occ_symbol(contract)[1].isoformat() < day:
                reason = 'expiry_liquidation_unresolved'
                break
            references.standard(contract, day)
            observed_mark(clock)
            exit_due = exit_at is not None and clock >= exit_at
            if not exit_due and clock < cutoff:
                continue
            close = session_close(clock)
            if clock + policy.latency_ns >= close:
                continue
            fill = archive.first_fill(contract, clock, side='sell',
                                      deadline_ns=min(clock + policy.entry_deadline_ns, close - 1))
            attempts.append({'clock_ns': clock, 'contract': contract, 'action': 'signal_exit' if exit_due else 'expiry_exit',
                             'status': 'filled' if fill else 'observed_unfilled'})
            proceeds = ledger.sell('position', fill)
            if proceeds is None:
                continue
            if exit_due or rolls >= max_rolls:
                terminal, reason = True, 'signal_exit' if exit_due else 'roll_limit'
                terminal_clock = clock
                break
            rolls += 1
            pending = not buy(fill['sip_timestamp'], is_roll=True)
        except CaptureUnavailable as exc:
            capture_complete, reason = False, 'capture_incomplete'
            attempts.append({'clock_ns': clock, 'status': 'uncaptured', 'reason': str(exc)})
            break
    ledger.reconcile()
    complete = started and terminal and not ledger.positions and capture_complete
    return {'proposal_id': proposal['proposal_id'], 'label_complete': complete, 'capture_complete': capture_complete,
            'status': reason, 'executed': started, 'rolls': rolls,
            'label_end_ns': max(ledger.events[-1]['sip_timestamp'], terminal_clock) if complete else None,
            'net_return': ledger.cash / ledger.initial - 1 if complete else None,
            'cash': ledger.cash, 'open_positions': ledger.positions, 'fills': ledger.events,
            'marks': marks, 'attempts': attempts,
            'mark_coverage_complete': all(m['status'] == 'observed' for m in marks),
            'portfolio_admission': False,
            'expiry_policy': 'observed liquidation before expiry; unresolved exercise is not assigned a synthetic return'}
