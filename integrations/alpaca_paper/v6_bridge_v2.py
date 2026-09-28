"""Version 2 paper execution: adjusted midpoint limits and independent orders.

V1 remains immutable for the original activation and outstanding legacy orders.
One process holds bridge.lock; independent means concurrent broker orders, not
concurrent POST threads. Every POST is durably journaled and reconciled.
"""
from datetime import datetime, timezone
from decimal import Decimal
import json
from time import monotonic

from integrations.alpaca_paper.v6_bridge import (
    Journal, broker_order_state, client_id, events_from_fresh_state, quote_dict,
    reconcile, stamp,
)
from integrations.alpaca_paper.v6_pricing import entry_preview
from integrations.alpaca_paper.v6_pricing_v2 import POLICY, execution_limit

TERMINAL = {'filled', 'canceled', 'expired', 'rejected'}


def dependencies(recorded, journal):
    contracts, keys, ownership = set(), set(), {}
    for row in recorded.values():
        source = json.loads(journal.get(row['event_id'])['payload'])['event']
        key = (source['position_key'], row['contract'])
        ownership[key] = ownership.get(key, Decimal(0)) + (
            Decimal(row['filled_qty'] or '0') * (1 if row['kind'] == 'entry' else -1))
        if row['state'] not in TERMINAL:
            contracts.add(row['contract'])
            keys.add(source['position_key'])
    return contracts, keys, ownership


def available_cash(account, recorded, journal):
    """Bound broker option BP by cash less outstanding long-option commitments.

    Broker BP already includes its holds: take the minimum, not BP minus holds.
    Cash provides an independent ceiling if broker holds lag a recent POST.
    Partial fills consume cash; only the unfilled remainder stays reserved.
    Pending cancellation keeps its reservation until confirmed terminal.
    """
    cash = Decimal(str(account.cash))
    bp = Decimal(str(account.options_buying_power))
    if not cash.is_finite() or not bp.is_finite():
        raise ValueError('invalid broker cash or options buying power')
    reserved = Decimal(0)
    for row in recorded.values():
        if row['kind'] == 'entry' and row['state'] not in TERMINAL:
            plan = json.loads(journal.get(row['event_id'])['payload'])['plan']
            remaining = Decimal(row['quantity']) - Decimal(row['filled_qty'] or '0')
            reserved += remaining * Decimal(plan['limit_price']) * 100
    return max(Decimal(0), min(bp, cash - reserved))


def order_plan(event: dict, *, account, broker_position, snapshot, contract, now: datetime, buying_power: Decimal | None = None) -> dict:
    """Validate one order from current broker state and a fresh OPRA snapshot."""
    status = str(getattr(account.status, "value", account.status))
    if status.upper() != "ACTIVE" or account.trading_blocked or account.account_blocked:
        raise ValueError("Alpaca paper account is not eligible")
    if int(account.options_trading_level or 0) < 2:
        raise ValueError("paper account lacks long-option level")
    if not contract.tradable or str(getattr(contract.status, "value", contract.status)).lower() != "active":
        raise ValueError("option contract is not active and tradable")
    if Decimal(str(contract.size)) != 100:
        raise ValueError("option contract multiplier is not 100")
    market = execution_limit(quote_dict(snapshot, received_at=now), now=now,
                        after=stamp(event.get("trigger_at", event["at"])),
                        side="buy" if event["kind"] == "entry" else "sell")
    if event["kind"] == "entry":
        if not 0 <= (now - stamp(event.get("signal_close", event["at"]))).total_seconds() <= 300:
            raise ValueError("entry event missed the five-minute broker window")
        if broker_position is not None:
            raise ValueError("broker already holds this contract")
        size = entry_preview(options_buying_power=str(account.options_buying_power if buying_power is None else buying_power),
                             size_fraction=float(event["size_fraction"]), mark=market)
        qty = size["preview_contracts"]
        if qty < 1:
            raise ValueError("no whole contract fits buying power and displayed ask")
        side, intent = "buy", "buy_to_open"
    else:
        if broker_position is None:
            raise ValueError("no broker position to close")
        whole = Decimal(str(broker_position.qty))
        if whole != whole.to_integral_value() or whole <= 0:
            raise ValueError('broker exit quantity must be positive whole contracts')
        qty = min(int(whole), int(snapshot.latest_quote.bid_size))
        if qty < 1:
            raise ValueError("no displayed bid size for broker exit")
        side, intent = "sell", "sell_to_close"
    return {"event_id": event["event_id"], "client_order_id": client_id(event["event_id"]),
            "contract": event["contract"], "qty": qty, "side": side,
            "position_intent": intent, "limit_price": market["limit_price"],
            "quote": market, "planned_at": now.isoformat(),
            "execution_policy": POLICY, "cancel_after_seconds": 120,
            "sizing": size if event['kind'] == 'entry' else None}


def process_events(events: list[dict], *, journal: Journal, trading, data,
                   expected_fingerprint: str, submit: bool = False,
                   now: datetime | None = None) -> list[dict]:
    """One poll. Preview is read-only; submission records intent before POST."""
    from alpaca.data.enums import OptionsFeed
    from alpaca.data.requests import OptionSnapshotRequest
    from alpaca.trading.enums import OrderSide, PositionIntent, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest
    started = monotonic()
    fixed_now = now
    now = now or datetime.now(timezone.utc)
    account, positions, recorded = reconcile(journal, trading, expected_fingerprint=expected_fingerprint,
                                            allow_pending=True)
    result = []
    pass_budget = available_cash(account, recorded, journal)
    terminal = {'filled', 'canceled', 'expired', 'rejected'}
    for row in recorded.values():
        if row['state'] in terminal:
            continue
        saved = journal.get(row['event_id'])
        payload = json.loads(saved['payload'])
        age = (now - stamp(payload['plan']['planned_at'])).total_seconds()
        # Cancel, then wait for a later confirmed terminal status before any
        # replacement. Partial fills remain real positions throughout.
        if submit and age >= payload['plan'].get('cancel_after_seconds', 60) and row['state'] != 'pending_cancel':
            trading.cancel_order_by_id(saved['broker_order_id'])
        result.append({'event_id': row['event_id'], 'status': 'awaiting_broker',
                       'filled_qty': row['filled_qty']})
    closed_keys = {e['position_key'] for e in events
                   if e.get('reason') == 'broker premium stop'}
    closing_contracts = {(e['position_key'], e['contract']) for e in events if e['kind'] == 'close'}
    preview_contracts, preview_keys = set(), set()
    for event in events:
        if monotonic() - started >= 20:
            result.append({'status': 'poll_budget_exhausted'})
            break
        event = dict(event)
        base = event['event_id']
        pending_contracts, pending_keys, ownership = dependencies(recorded, journal)
        attempts = [row for row in recorded.values()
                    if row['event_id'] == base or row['event_id'].startswith(base + '|attempt|')]
        if event['kind'] == 'entry' and (event['position_key'] in closed_keys
                                        or (event['position_key'], event['contract']) in closing_contracts):
            result.append({'event_id': base, 'status': 'superseded'})
            continue
        if attempts and event['kind'] == 'entry':
            result.append({"event_id": event["event_id"], "status": "recorded"})
            continue
        if (event['contract'] in pending_contracts | preview_contracts
                or event['position_key'] in pending_keys | preview_keys):
            result.append({'event_id': base, 'status': 'awaiting_dependency'})
            continue
        if event['kind'] == 'close' and attempts and event['contract'] in positions:
            event['event_id'] = base + '|attempt|' + str(len(attempts))
        if event['kind'] == 'entry' and event.get('roll', 0):
            prior = [e['contract'] for e in events if e['position_key'] == event['position_key']
                     and e['kind'] == 'entry' and e.get('roll', 0) < event['roll']]
            if any(contract in positions for contract in prior):
                result.append({'event_id': base, 'status': 'awaiting_roll_close'})
                continue
        if event["kind"] == "entry" and any(
                row["kind"] == "entry" and row["contract"] == event["contract"]
                and event['contract'] in positions
                for row in recorded.values()):
            result.append({'event_id': base, 'status': 'blocked',
                           'reason': 'broker already holds this contract'})
            continue
        if event["kind"] == "close" and (event["contract"] not in positions or
                ownership.get((event['position_key'], event['contract']), 0) <= 0):
            result.append({"event_id": event["event_id"], "status": "no_broker_position"})
            continue
        decision_now = fixed_now or datetime.now(timezone.utc)
        if event['kind'] == 'entry' and not 0 <= (
                decision_now - stamp(event.get('signal_close', event['at']))).total_seconds() <= 300:
            result.append({'event_id': base, 'status': 'blocked',
                           'reason': 'entry event missed the five-minute broker window'})
            continue
        try:
            contract = trading.get_option_contract(event["contract"])
            snapshot = data.get_option_snapshot(OptionSnapshotRequest(
                symbol_or_symbols=event["contract"], feed=OptionsFeed.OPRA))[event["contract"]]
            planned_at = datetime.now(timezone.utc) if fixed_now is None else now
            plan = order_plan(event, account=account, broker_position=positions.get(event["contract"]),
                              snapshot=snapshot, contract=contract, now=planned_at,
                              buying_power=min(pass_budget, available_cash(account, recorded, journal)))
        except (ValueError, KeyError, TypeError) as exc:
            result.append({"event_id": event["event_id"], "status": "blocked", "reason": str(exc)})
            continue
        if not submit:
            result.append({"event_id": event["event_id"], "status": "preview", "plan": plan})
            preview_contracts.add(event['contract'])
            preview_keys.add(event['position_key'])
            if event['kind'] == 'entry':
                pass_budget -= Decimal(plan['limit_price']) * plan['qty'] * 100
            continue
        journal.intent(event, plan)
        side = OrderSide.BUY if event["kind"] == "entry" else OrderSide.SELL
        intent = PositionIntent.BUY_TO_OPEN if event["kind"] == "entry" else PositionIntent.SELL_TO_CLOSE
        request = LimitOrderRequest(symbol=plan["contract"], qty=plan["qty"], side=side,
                                    time_in_force=TimeInForce.DAY, client_order_id=plan["client_order_id"],
                                    position_intent=intent, limit_price=float(plan["limit_price"]))
        try:
            order = trading.submit_order(order_data=request)
        except Exception:
            journal.update(event["event_id"], state="uncertain_post")
            raise
        state = broker_order_state(order)
        journal.update(event["event_id"], state=state["status"], broker_order_id=state["id"],
                       filled_qty=state["filled_qty"], filled_avg_price=state["filled_avg_price"])
        result.append({"event_id": event["event_id"], "status": state["status"],
                       "broker_order_id": state["id"]})
        if event['kind'] == 'entry':
            # No same-poll credit for cancels, proceeds or lagging account updates.
            pass_budget -= Decimal(plan['limit_price']) * plan['qty'] * 100
        account, positions, recorded = reconcile(
            journal, trading, expected_fingerprint=expected_fingerprint, allow_pending=True)
    return result
