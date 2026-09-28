"""Restart-safe fixed-anchor limit ladders, with confirmed cancel/new replacement.

The original order journal remains authoritative for actual fills. A separate
chain journal protects ownership/cash across cancellation gaps. Legacy orders
keep their saved timeout and never acquire a new ladder retroactively.
"""
from datetime import datetime, timezone
from decimal import Decimal
import json
from time import monotonic

from integrations.alpaca_paper.v6_bridge import (
    Journal as BaseJournal, broker_order_state, client_id, events_from_fresh_state,
    quote_dict, reconcile, stamp,
)
from integrations.alpaca_paper.v6_bridge_v2 import dependencies, order_plan as old_plan
from integrations.alpaca_paper.v6_pricing import entry_preview, mark_limit
from integrations.alpaca_paper.v6_pricing_v3 import POLICY, WAITS, execution_limit

TERMINAL = {'filled', 'canceled', 'expired', 'rejected'}
MAX_CHAIN_SECONDS = 300  # stale restart/cancellation gaps cannot revive an old ladder


class Journal(BaseJournal):
    def __init__(self, path):
        super().__init__(path)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS step_chains '
                       '(base TEXT PRIMARY KEY, state TEXT NOT NULL, payload TEXT NOT NULL)')

    def chains(self):
        with self.connect() as db:
            return {base: dict(json.loads(payload), state=state) for base, state, payload
                    in db.execute('SELECT base,state,payload FROM step_chains ORDER BY rowid')}

    def save_chain(self, chain):
        with self.connect() as db:
            db.execute('INSERT INTO step_chains VALUES(?,?,?) ON CONFLICT(base) DO UPDATE '
                       'SET state=excluded.state,payload=excluded.payload',
                       (chain['event']['event_id'], chain['state'], json.dumps(chain, sort_keys=True)))


def rows_for(chain, recorded, journal):
    base = chain['event']['event_id']
    rows = []
    for row in recorded.values():
        plan = json.loads(journal.get(row['event_id'])['payload'])['plan']
        if plan.get('chain_base') == base:
            rows.append((row, plan))
    rows.sort(key=lambda pair: pair[1]['step'])
    if [p['step'] for r, p in rows] != list(range(len(rows))):
        raise ValueError('Non-contiguous ladder journal')
    return rows


def remaining(chain, rows):
    filled = sum((Decimal(row['filled_qty'] or '0') for row, _ in rows), Decimal(0))
    result = Decimal(chain['plan']['qty']) - filled
    if result < 0 or result != result.to_integral_value():
        raise ValueError('Invalid cumulative ladder quantity')
    return int(result)


def available_cash(account, recorded, journal, *, exclude=None):
    cash, bp = Decimal(str(account.cash)), Decimal(str(account.options_buying_power))
    if not cash.is_finite() or not bp.is_finite():
        raise ValueError('Invalid broker cash or buying power')
    reserved = Decimal(0)
    for base, chain in journal.chains().items():
        if base == exclude or chain['state'] != 'active' or chain['event']['kind'] != 'entry':
            continue
        reserved += remaining(chain, rows_for(chain, recorded, journal)) * Decimal(chain['plan']['step_limits'][3]) * 100
    for row in recorded.values():
        plan = json.loads(journal.get(row['event_id'])['payload'])['plan']
        if not plan.get('chain_base') and row['kind'] == 'entry' and row['state'] not in TERMINAL:
            reserved += (Decimal(row['quantity']) - Decimal(row['filled_qty'] or '0')) * Decimal(plan['limit_price']) * 100
    return max(Decimal(0), min(bp, cash - reserved))


def order_plan(event, *, account, broker_position, snapshot, contract, now, buying_power=None):
    # Reuse unchanged eligibility, original entry deadline and broker checks.
    plan = old_plan(event, account=account, broker_position=broker_position,
                    snapshot=snapshot, contract=contract, now=now, buying_power=buying_power)
    market = execution_limit(quote_dict(snapshot, received_at=now), now=now,
        after=stamp(event.get('trigger_at', event['at'])), side=plan['side'])
    if event['kind'] == 'entry':
        sizing = entry_preview(options_buying_power=str(account.options_buying_power if buying_power is None else buying_power),
            size_fraction=float(event['size_fraction']), mark=dict(market, limit_price=market['step_limits'][3]))
        if sizing['preview_contracts'] < 1:
            raise ValueError('No whole contract fits final-step allocation')
        plan.update(qty=sizing['preview_contracts'], sizing=sizing)
    plan.update(limit_price=market['limit_price'], quote=market, execution_policy=POLICY,
                step_limits=market['step_limits'], midpoint=market['midpoint'],
                cancel_after_seconds=WAITS[0], step=0, chain_base=event['event_id'])
    return plan


def process_events(events, *, journal, trading, data, expected_fingerprint,
                   submit=False, now=None):
    from alpaca.data.enums import OptionsFeed
    from alpaca.data.requests import OptionSnapshotRequest
    from alpaca.trading.enums import OrderSide, PositionIntent, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest
    started = monotonic()
    fixed_now = now
    clock = lambda: fixed_now or datetime.now(timezone.utc)
    account, positions, recorded = reconcile(journal, trading,
        expected_fingerprint=expected_fingerprint, allow_pending=True)
    result = []
    cash_spent = Decimal(0)  # protects same-poll decisions against lagging balances
    initial_cash = Decimal(str(account.cash))
    close_keys = {(e['position_key'], e['contract']) for e in events if e['kind'] == 'close'}
    stop_keys = {e['position_key'] for e in events if e.get('reason') == 'broker premium stop'}

    def snapshot(event):
        return data.get_option_snapshot(OptionSnapshotRequest(
            symbol_or_symbols=event['contract'], feed=OptionsFeed.OPRA))[event['contract']]

    def post(event, plan):
        nonlocal account, positions, recorded, cash_spent
        journal.intent(event, plan)
        request = LimitOrderRequest(symbol=plan['contract'], qty=plan['qty'],
            side=OrderSide.BUY if event['kind'] == 'entry' else OrderSide.SELL,
            position_intent=PositionIntent.BUY_TO_OPEN if event['kind'] == 'entry' else PositionIntent.SELL_TO_CLOSE,
            time_in_force=TimeInForce.DAY, client_order_id=plan['client_order_id'],
            limit_price=float(plan['limit_price']))
        try:
            order = trading.submit_order(order_data=request)
        except Exception:
            journal.update(event['event_id'], state='uncertain_post')
            raise
        state = broker_order_state(order)
        journal.update(event['event_id'], state=state['status'], broker_order_id=state['id'],
            filled_qty=state['filled_qty'], filled_avg_price=state['filled_avg_price'])
        if event['kind'] == 'entry':
            cash_spent += Decimal(plan['step_limits'][3]) * plan['qty'] * 100
        result.append(dict(event_id=event['event_id'], status=state['status'],
                           step=plan['step'] + 1, broker_order_id=state['id']))
        account, positions, recorded = reconcile(journal, trading,
            expected_fingerprint=expected_fingerprint, allow_pending=True)

    # Outstanding legacy orders retain their saved cancellation policy.
    for row in recorded.values():
        saved = journal.get(row['event_id']);plan = json.loads(saved['payload'])['plan']
        if row['state'] in TERMINAL or plan.get('chain_base'):
            continue
        if submit and row['state'] != 'pending_cancel' and (clock()-stamp(plan['planned_at'])).total_seconds() >= plan.get('cancel_after_seconds', 60):
            trading.cancel_order_by_id(saved['broker_order_id'])
        result.append(dict(event_id=row['event_id'], status='awaiting_legacy_order'))

    for base, chain in journal.chains().items():
        if chain['state'] != 'active':
            continue
        if monotonic()-started >= 20:
            result.append(dict(status='poll_budget_exhausted'));break
        event = chain['event'];rows = rows_for(chain, recorded, journal)
        qty = remaining(chain, rows)
        age = (clock()-stamp(chain['plan']['planned_at'])).total_seconds()
        superseded = event['kind'] == 'entry' and ((event['position_key'], event['contract']) in close_keys or event['position_key'] in stop_keys)
        stop = superseded or age >= MAX_CHAIN_SECONDS
        latest, last_plan = rows[-1] if rows else (None, None)
        if latest and latest['state'] not in TERMINAL:
            due = (clock()-stamp(last_plan['planned_at'])).total_seconds() >= WAITS[last_plan['step']]
            if submit and (stop or due) and latest['state'] != 'pending_cancel':
                chain['cancel_requested_for'] = latest['event_id']
                if stop:chain['stop_requested'] = True
                journal.save_chain(chain)  # persist BEFORE cancellation, including races/restarts
                trading.cancel_order_by_id(journal.get(latest['event_id'])['broker_order_id'])
            result.append(dict(event_id=base, status='awaiting_broker', remaining=qty, step=last_plan['step']+1))
            continue
        done = (not qty or stop or chain.get('stop_requested') or
            (not rows and event['kind'] == 'entry' and not 0 <=
             (clock()-stamp(event.get('signal_close',event['at']))).total_seconds() <= 300) or
            (latest is not None and (latest['state'] != 'canceled' or last_plan['step'] == 3 or
                                     chain.get('cancel_requested_for') != latest['event_id'])))
        if done:
            if submit:
                chain.update(state='done', finished_at=clock().isoformat(), remaining=qty)
                journal.save_chain(chain)
            result.append(dict(event_id=base, status='ladder_finished', remaining=qty))
            continue
        step = len(rows)
        attempt = dict(event, event_id=base if step == 0 else base+'|step|'+str(step))
        plan = dict(chain['plan'], event_id=attempt['event_id'], client_order_id=client_id(attempt['event_id']),
                    qty=qty, step=step, planned_at=clock().isoformat(),
                    limit_price=chain['plan']['step_limits'][step], cancel_after_seconds=WAITS[step])
        try:
            snap = snapshot(event);at = clock()
            # Fresh market validation does not move the frozen midpoint anchor.
            mark_limit(dict(quote_dict(snap, received_at=at), mark=None), now=at,
                       after=stamp(event.get('trigger_at', event['at'])))
            contract = trading.get_option_contract(event['contract'])
            if (not contract.tradable or str(getattr(contract.status,'value',contract.status)).lower() != 'active'
                    or Decimal(str(contract.size)) != 100):
                raise ValueError('Option is no longer active, tradable and standard')
            if (str(getattr(account.status,'value',account.status)).upper() != 'ACTIVE'
                    or account.trading_blocked or account.account_blocked or int(account.options_trading_level or 0)<2):
                raise ValueError('Account is no longer eligible')
            contracts, keys, owned = dependencies(recorded, journal)
            if event['contract'] in contracts or event['position_key'] in keys:
                raise ValueError('Replacement awaits another broker dependency')
            displayed = snap.latest_quote.ask_size if event['kind']=='entry' else snap.latest_quote.bid_size
            if qty > int(displayed):raise ValueError('Replacement exceeds displayed quantity')
            if event['kind'] == 'entry':
                funds = min(available_cash(account, recorded, journal, exclude=base), initial_cash-cash_spent)
                if Decimal(plan['limit_price'])*qty*100 > funds:
                    raise ValueError('Replacement exceeds available cash')
            elif (event['contract'] not in positions or
                  qty > Decimal(str(positions[event['contract']].qty)) or
                  qty > owned.get((event['position_key'],event['contract']),0)):
                raise ValueError('Replacement exceeds owned holding')
            plan['planned_at'] = at.isoformat()
            if (at-stamp(chain['plan']['planned_at'])).total_seconds() >= MAX_CHAIN_SECONDS:
                raise ValueError('Ladder expired during replacement preparation')
        except (ValueError, KeyError, TypeError) as exc:
            result.append(dict(event_id=base,status='replacement_blocked',reason=str(exc)));continue
        if submit:post(attempt,plan)
        else:result.append(dict(event_id=attempt['event_id'],status='preview_replacement',plan=plan))

    preview_contracts, preview_keys = set(), set()
    preview_budget = available_cash(account, recorded, journal)
    for source in events:
        if monotonic()-started >= 20:
            result.append(dict(status='poll_budget_exhausted'));break
        event = dict(source);base = event['event_id']
        chains = journal.chains()
        if base in chains or any(r['event_id']==base or r['event_id'].startswith(base+'|attempt|') for r in recorded.values()):
            continue  # completed ladders/legacy events never restart automatically
        contracts, keys, owned = dependencies(recorded, journal)
        for c in chains.values():
            if c['state']=='active':
                contracts.add(c['event']['contract']);keys.add(c['event']['position_key'])
        if event['kind']=='entry' and ((event['position_key'],event['contract']) in close_keys or event['position_key'] in stop_keys):
            result.append(dict(event_id=base,status='superseded'));continue
        if event['contract'] in contracts|preview_contracts or event['position_key'] in keys|preview_keys:
            result.append(dict(event_id=base,status='awaiting_dependency'));continue
        if event['kind']=='entry' and event.get('roll',0):
            prior = [e['contract'] for e in events if e['position_key']==event['position_key'] and e['kind']=='entry' and e.get('roll',0)<event['roll']]
            if any(c in positions for c in prior):
                result.append(dict(event_id=base,status='awaiting_roll_close'));continue
        if event['kind']=='close' and owned.get((event['position_key'],event['contract']),0)<=0:
            result.append(dict(event_id=base,status='no_broker_position'));continue
        at = clock()
        if event['kind']=='entry' and not 0 <= (at-stamp(event.get('signal_close',event['at']))).total_seconds() <= 300:
            result.append(dict(event_id=base,status='blocked',reason='entry event missed the five-minute broker window'));continue
        try:
            contract=trading.get_option_contract(event['contract']);snap=snapshot(event)
            plan=order_plan(event,account=account,broker_position=positions.get(event['contract']),
                snapshot=snap,contract=contract,now=clock(),buying_power=min(preview_budget,
                available_cash(account,recorded,journal),initial_cash-cash_spent))
        except (ValueError,KeyError,TypeError) as exc:
            result.append(dict(event_id=base,status='blocked',reason=str(exc)));continue
        if submit:
            journal.save_chain(dict(event=event,plan=plan,state='active'))
            post(event,plan)
        else:
            result.append(dict(event_id=base,status='preview',plan=plan))
            preview_contracts.add(event['contract']);preview_keys.add(event['position_key'])
            if event['kind']=='entry':preview_budget-=Decimal(plan['step_limits'][3])*plan['qty']*100
    return result
