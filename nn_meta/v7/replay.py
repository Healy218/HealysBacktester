"""Observed-quote label replay with explicit rolls, failed fills and censoring.

Individual proposal labels use one unit of allocated capital. A separate
portfolio must allocate the shared five slots; these returns are not summed
as independently funded positions.
"""
import pandas as pd
from dataclasses import asdict
from options.paper_risk import V7_OPTION_RISK, premium_stop, in_the_money

from nn_meta.v7.execution import CashLedger, QuotePolicy, QuoteUnavailable, CaptureUnavailable, fill_clock


def replay(proposal, clocks, archive, references, *, select_contract, expiry_cutoff,
           session_close, policy=QuotePolicy(), max_rolls=60, underlying_mark=None):
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
    risk_exit = None

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
            equity = ledger.cash + position['quantity'] * policy.multiplier * value['price']
            marks.append({'clock_ns': clock, 'contract': position['contract'], 'status': 'observed',
                          'quote_as_of_ns': quote_clock, 'equity': equity, **value})
            return value
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
            mark = observed_mark(clock)
            if risk_exit is None and mark is not None:
                assessment = premium_stop(position['entry_midpoint'], mark['price'], V7_OPTION_RISK)
                if assessment['triggered']:
                    risk_exit = dict(reason='option_midpoint_stop', clock_ns=clock,
                                     quote_timestamp_ns=mark['sip_timestamp'], **assessment)
            exit_due = exit_at is not None and clock >= exit_at
            if not exit_due and risk_exit is None and clock < cutoff:
                continue
            # Classify ITM at the configured 15-minute pre-close cutoff using
            # a causal observed stock price. Unknown is never treated as OTM.
            if not exit_due and risk_exit is None and clock >= cutoff:
                if underlying_mark is None:
                    raise CaptureUnavailable('ITM expiry exit requires an observed underlying mark')
                spot = underlying_mark(proposal['symbol'], clock)
                if (not isinstance(spot, dict) or type(spot.get('sip_timestamp')) is not int
                        or not 0 <= clock-spot['sip_timestamp'] <= policy.max_mark_age_ns):
                    raise QuoteUnavailable('No fresh causal underlying mark for ITM expiry exit')
                _, _, right, strike = parse_occ_symbol(contract)
                if in_the_money(right, strike, spot['price']):
                    risk_exit = dict(reason='itm_expiry_exit', clock_ns=clock,
                                     underlying_mark=spot, strike=strike, right=right)
            close = session_close(clock)
            if clock >= close or ((risk_exit is None or mark is None) and clock + policy.latency_ns >= close):
                continue
            if risk_exit is not None and mark is not None:
                # A valid observed midpoint is sufficient for this paper sale.
                # Do not backdate the decision to an older quote: keep both times.
                fill = dict(mark, contract=contract, side='sell', decision_ns=clock,
                            execution_ns=clock, simulated=True)
            else:
                fill = archive.first_fill(contract, clock, side='sell',
                                          deadline_ns=min(clock + policy.entry_deadline_ns, close - 1))
            exit_reason = risk_exit['reason'] if risk_exit is not None else ('signal_exit' if exit_due else 'expiry_exit')
            attempts.append({'clock_ns': clock, 'contract': contract, 'action': exit_reason,
                             'status': 'filled' if fill else 'observed_unfilled'})
            proceeds = ledger.sell('position', fill)
            if proceeds is None:
                continue
            if exit_due or risk_exit is not None or rolls >= max_rolls:
                terminal, reason = True, exit_reason if (exit_due or risk_exit is not None) else 'roll_limit'
                terminal_clock = clock
                break
            rolls += 1
            pending = not buy(fill['sip_timestamp'], is_roll=True)
        except CaptureUnavailable as exc:
            capture_complete, reason = False, 'capture_incomplete'
            attempts.append({'clock_ns': clock, 'status': 'uncaptured', 'reason': str(exc)})
            break
        except QuoteUnavailable as exc:
            # A captured but stale/invalid underlying quote cannot classify an
            # expiry as OTM. Keep the position and retry at the next clock.
            attempts.append({'clock_ns': clock, 'status': 'unavailable', 'reason': str(exc)})
    ledger.reconcile()
    complete = started and terminal and not ledger.positions and capture_complete
    return {'proposal_id': proposal['proposal_id'], 'label_complete': complete, 'capture_complete': capture_complete,
            'status': reason, 'executed': started, 'rolls': rolls,
            'label_end_ns': max(fill_clock(ledger.events[-1]), terminal_clock) if complete else None,
            'net_return': ledger.cash / ledger.initial - 1 if complete else None,
            'cash': ledger.cash, 'open_positions': ledger.positions, 'fills': ledger.events,
            'marks': marks, 'attempts': attempts,
            'mark_coverage_complete': all(m['status'] == 'observed' for m in marks),
            'option_risk_policy': asdict(V7_OPTION_RISK), 'risk_exit': risk_exit,
            'portfolio_admission': False,
            'expiry_policy': 'observed liquidation before expiry; unresolved exercise is not assigned a synthetic return'}
