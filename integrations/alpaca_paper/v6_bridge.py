"""Broker-side V6 paper order bridge; simulator records are signals, never fills.

Only the dedicated Alpaca paper keys are accepted by the CLI. Every proposed
order is tied to a future structured V6 position or close event in the fresh
state, then reconciled against the broker before submission.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import os

from integrations.alpaca_paper.v6_pricing import entry_preview, mark_limit


def stamp(value: str | datetime) -> datetime:
    value = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("event timestamp must be timezone aware")
    return value.astimezone(timezone.utc)


def client_id(event_id: str) -> str:
    return "v6p-" + hashlib.sha256(event_id.encode()).hexdigest()[:36]


def events_from_fresh_state(database: Path, *, activated_at: datetime) -> list[dict]:
    """Read only structured positions and leg-close records after activation."""
    database = Path(database)
    if not database.is_file() or database.is_symlink():
        raise ValueError("fresh V6 position database is missing")
    events = []
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        positions = [json.loads(row[0]) for row in db.execute("SELECT payload FROM positions ORDER BY key")]
        durable = bool(db.execute("SELECT 1 FROM sqlite_master WHERE name='broker_source_entries'").fetchone())
        entries = [json.loads(row[0]) for row in db.execute(
            "SELECT payload FROM broker_source_entries ORDER BY key,roll")] if durable else []
        closes = [(key, stamp(recorded_at), json.loads(payload)) for key, recorded_at, payload in
                  db.execute("SELECT key,recorded_at,payload FROM events WHERE kind='close' ORDER BY recorded_at,key")]
    for position in positions:
        opened = stamp(position["opened_at"])
        if opened < activated_at:
            raise ValueError("fresh scanner contains a pre-activation position")
        key = position["key"]
        if durable:
            legs = [e for e in entries if e['position_key'] == key]
            expected_rolls = list(range(int(position.get('rolls', 0)) + 1))
            if sorted(e['roll'] for e in legs) != expected_rolls:
                raise ValueError('durable scanner entry history is incomplete')
            current = next(e for e in legs if e['roll'] == expected_rolls[-1])
            if current['contract'] != position['contract']:
                raise ValueError('durable scanner contract differs from position')
            continue
        rolls = int(position.get("rolls", 0))
        if rolls < 0 or rolls > 1:
            raise ValueError("unreconciled multi-roll position requires review")
        first_contract = (position["legs"][0]["contract"] if position.get("legs") else
                          position["contract"])
        events.append({"event_id": f"{key}|entry|0", "kind": "entry", "position_key": key,
                       "contract": first_contract, "at": opened.isoformat(),
                       "size_fraction": position["size_fraction"], "roll": 0})
        if rolls:
            quote = position.get("entry_quote") or {}
            opened_roll = stamp(quote["received_at"])
            if opened_roll < activated_at:
                raise ValueError("roll entry predates broker activation")
            events.append({"event_id": f"{key}|entry|1", "kind": "entry", "position_key": key,
                           "contract": position["contract"], "at": opened_roll.isoformat(),
                           "size_fraction": position["size_fraction"], "roll": 1})
    for entry in entries:
        opened = stamp(entry['at'])
        if opened < activated_at:
            raise ValueError('durable entry predates broker activation')
        events.append(entry)
    for key, recorded, leg in closes:
        if recorded < activated_at:
            continue
        if "|leg-close|" not in key or not key.rsplit("|", 1)[-1].isdigit():
            raise ValueError("malformed structured V6 close event")
        events.append({"event_id": key, "kind": "close", "position_key": key.split("|leg-close|")[0],
                       "contract": leg["contract"], "at": recorded.isoformat(),
                       "trigger_at": leg["trigger_at"], "reason": leg["reason"]})
    order = {"close": 0, "entry": 1}
    return sorted(events, key=lambda row: (row["at"], order[row["kind"]], row["event_id"]))


def quote_dict(snapshot, *, received_at: datetime) -> dict:
    quote = snapshot.latest_quote
    if quote is None:
        raise ValueError("option snapshot has no quote")
    result = {"bid": quote.bid_price, "ask": quote.ask_price,
              "bid_size": quote.bid_size, "ask_size": quote.ask_size,
              "sip_timestamp_ns": int(stamp(quote.timestamp).timestamp() * 1_000_000_000),
              "received_at": received_at.isoformat()}
    mark = getattr(snapshot, "mark_price", None)
    if mark is not None:
        result["mark"] = mark
    trade = snapshot.latest_trade
    if trade is not None:
        result["last"] = trade.price
    return result


def order_plan(event: dict, *, account, broker_position, snapshot, contract, now: datetime) -> dict:
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
    market = mark_limit(quote_dict(snapshot, received_at=now), now=now,
                        after=stamp(event.get("trigger_at", event["at"])))
    if event["kind"] == "entry":
        if not 0 <= (now - stamp(event.get("signal_close", event["at"]))).total_seconds() <= 300:
            raise ValueError("entry event missed the five-minute broker window")
        if broker_position is not None:
            raise ValueError("broker already holds this contract")
        size = entry_preview(options_buying_power=str(account.options_buying_power),
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
            "quote": market, "planned_at": now.isoformat()}


class Journal:
    """Append the intent before POST so an uncertain response cannot duplicate it."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and (self.path.is_symlink() or self.path.stat().st_mode & 0o077):
            raise ValueError("broker journal must be a private regular file")
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS orders (
                event_id TEXT PRIMARY KEY, client_order_id TEXT UNIQUE NOT NULL,
                kind TEXT NOT NULL, contract TEXT NOT NULL, quantity INTEGER NOT NULL,
                state TEXT NOT NULL, broker_order_id TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, payload TEXT NOT NULL,
                filled_qty TEXT, filled_avg_price TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS observations (
                ordinal INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL,
                observed_at TEXT NOT NULL, state TEXT NOT NULL, broker_order_id TEXT,
                filled_qty TEXT, filled_avg_price TEXT)""")
        os.chmod(self.path, 0o600)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA busy_timeout=5000")
        return db

    def get(self, event_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT client_order_id,kind,contract,quantity,state,broker_order_id,payload "
                             "FROM orders WHERE event_id=?", (event_id,)).fetchone()
        if row is None:
            return None
        return dict(zip(("client_order_id", "kind", "contract", "quantity", "state",
                         "broker_order_id", "payload"), row))

    def all(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT event_id,client_order_id,kind,contract,quantity,state,filled_qty,filled_avg_price "
                              "FROM orders ORDER BY created_at,event_id").fetchall()
        return [dict(zip(("event_id", "client_order_id", "kind", "contract", "quantity", "state",
                          "filled_qty", "filled_avg_price"), row))
                for row in rows]

    def intent(self, event: dict, plan: dict) -> None:
        at = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       (event["event_id"], plan["client_order_id"], event["kind"],
                        plan["contract"], plan["qty"], "intent", None, at, at,
                        json.dumps({"event": event, "plan": plan}, sort_keys=True), None, None))
            db.execute("INSERT INTO observations (event_id,observed_at,state) VALUES (?,?,?)",
                       (event["event_id"], at, "intent"))

    def update(self, event_id: str, *, state: str, broker_order_id: str | None = None,
               filled_qty: str | None = None, filled_avg_price: str | None = None) -> None:
        with self.connect() as db:
            at = datetime.now(timezone.utc).isoformat()
            result = db.execute("UPDATE orders SET state=?,broker_order_id=COALESCE(?,broker_order_id),"
                                "filled_qty=COALESCE(?,filled_qty),"
                                "filled_avg_price=COALESCE(?,filled_avg_price),updated_at=? WHERE event_id=?",
                                (state, broker_order_id, filled_qty, filled_avg_price, at, event_id))
            if result.rowcount != 1:
                raise ValueError("broker journal event missing")
            db.execute("INSERT INTO observations (event_id,observed_at,state,broker_order_id,filled_qty,filled_avg_price) "
                       "VALUES (?,?,?,?,?,?)",
                       (event_id, at, state, broker_order_id, filled_qty, filled_avg_price))


def broker_order_state(order) -> dict:
    return {"id": str(order.id), "client_order_id": str(order.client_order_id),
            "symbol": str(order.symbol), "status": str(getattr(order.status, "value", order.status)),
            "qty": str(order.qty), "filled_qty": str(order.filled_qty or 0),
            "filled_avg_price": str(order.filled_avg_price) if order.filled_avg_price is not None else None}


def reconcile(journal: Journal, trading, *, expected_fingerprint: str,
              allow_pending: bool = False) -> tuple[object, dict, dict]:
    """Fail closed on foreign broker state or any unresolved bridge order."""
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest
    account = trading.get_account()
    fingerprint = hashlib.sha256(str(account.id).encode()).hexdigest()
    if fingerprint != expected_fingerprint:
        raise ValueError("paper account fingerprint changed")
    positions = {position.symbol: position for position in trading.get_all_positions()}
    open_orders = trading.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=500))
    if len(open_orders) == 500:
        raise ValueError("open order response may be truncated")
    recorded = {row["client_order_id"]: row for row in journal.all()}
    for order in open_orders:
        if str(order.client_order_id) not in recorded:
            raise ValueError("unrecognized broker open order")
    open_by_client = {str(order.client_order_id): order for order in open_orders}
    for row in recorded.values():
        if row['state'] in ('filled', 'canceled', 'expired', 'rejected') and row['filled_qty'] is not None:
            # Terminal fills are immutable journal facts. Re-fetching all
            # historic orders on every 15-second poll exhausts the API budget.
            continue
        try:
            order = open_by_client.get(row['client_order_id'])
            if order is None:
                order = trading.get_order_by_client_id(row["client_order_id"])
        except Exception as exc:
            # An intent may have been durably recorded just before a failed POST.
            # Ambiguous requests require operator review; never retry blindly.
            raise ValueError("journal order cannot be resolved at broker") from exc
        state = broker_order_state(order)
        if state["client_order_id"] != row["client_order_id"] or state["symbol"] != row["contract"]:
            raise ValueError("broker order differs from journal")
        journal.update(row["event_id"], state=state["status"], broker_order_id=state["id"],
                       filled_qty=state["filled_qty"], filled_avg_price=state["filled_avg_price"])
        if (state["status"] not in ("filled", "canceled", "expired", "rejected")
                and not allow_pending):
            raise ValueError("broker order remains unresolved")
        filled = Decimal(state['filled_qty'])
        if not 0 <= filled <= row['quantity'] or filled != filled.to_integral_value():
            raise ValueError('invalid broker fill quantity')
        if filled not in (0, row['quantity']) and not allow_pending:
            raise ValueError("partial broker fill requires review")
    entry_contracts = {row["contract"] for row in recorded.values() if row["kind"] == "entry"}
    if set(positions) - entry_contracts:
        raise ValueError("broker holds a position outside the fresh V6 bridge")
    expected = {}
    for row in journal.all():
        filled = Decimal(str(row["filled_qty"] or "0"))
        if filled != filled.to_integral_value() or filled < 0:
            raise ValueError("broker filled quantity is not whole contracts")
        direction = 1 if row["kind"] == "entry" else -1
        expected[row["contract"]] = expected.get(row["contract"], 0) + direction * int(filled)
    # Re-read positions after order observations to avoid comparing an old
    # position snapshot with a just-received fill. Races still fail closed.
    positions = {position.symbol: position for position in trading.get_all_positions()}
    if set(positions) - entry_contracts:
        raise ValueError('broker holds a position outside the fresh V6 bridge')
    for symbol in entry_contracts:
        actual = Decimal(str(positions[symbol].qty)) if symbol in positions else Decimal(0)
        if actual != expected.get(symbol, 0):
            raise ValueError("broker position differs from recorded fills")
    recorded = {row['client_order_id']: row for row in journal.all()}
    return trading.get_account(), positions, recorded


def process_events(events: list[dict], *, journal: Journal, trading, data,
                   expected_fingerprint: str, submit: bool = False,
                   now: datetime | None = None) -> list[dict]:
    """One poll. Preview is read-only; submission records intent before POST."""
    from alpaca.data.enums import OptionsFeed
    from alpaca.data.requests import OptionSnapshotRequest
    from alpaca.trading.enums import OrderSide, PositionIntent, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest
    fixed_now = now
    now = now or datetime.now(timezone.utc)
    account, positions, recorded = reconcile(journal, trading, expected_fingerprint=expected_fingerprint,
                                            allow_pending=True)
    result = []
    terminal = {'filled', 'canceled', 'expired', 'rejected'}
    for row in recorded.values():
        if row['state'] in terminal:
            continue
        saved = journal.get(row['event_id'])
        payload = json.loads(saved['payload'])
        age = (now - stamp(payload['plan']['planned_at'])).total_seconds()
        # Cancel, then wait for a later confirmed terminal status before any
        # replacement. Partial fills remain real positions throughout.
        if submit and age >= 60 and row['state'] != 'pending_cancel':
            trading.cancel_order_by_id(saved['broker_order_id'])
        result.append({'event_id': row['event_id'], 'status': 'awaiting_broker',
                       'filled_qty': row['filled_qty']})
    if result:
        return result
    closed_keys = {e['position_key'] for e in events
                   if e.get('reason') == 'broker premium stop'}
    closing_contracts = {(e['position_key'], e['contract']) for e in events if e['kind'] == 'close'}
    ownership = {}
    for row in recorded.values():
        source = json.loads(journal.get(row['event_id'])['payload'])['event']
        key = (source['position_key'], row['contract'])
        ownership[key] = ownership.get(key, Decimal(0)) + (
            Decimal(row['filled_qty'] or '0') * (1 if row['kind'] == 'entry' else -1))
    for event in events:
        event = dict(event)
        base = event['event_id']
        attempts = [row for row in recorded.values()
                    if row['event_id'] == base or row['event_id'].startswith(base + '|attempt|')]
        if event['kind'] == 'entry' and (event['position_key'] in closed_keys
                                        or (event['position_key'], event['contract']) in closing_contracts):
            result.append({'event_id': base, 'status': 'superseded'})
            continue
        if attempts and event['kind'] == 'entry':
            result.append({"event_id": event["event_id"], "status": "recorded"})
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
            raise ValueError("multiple V6 positions selected the same option contract")
        if event["kind"] == "close" and (event["contract"] not in positions or
                ownership.get((event['position_key'], event['contract']), 0) <= 0):
            result.append({"event_id": event["event_id"], "status": "no_broker_position"})
            continue
        try:
            contract = trading.get_option_contract(event["contract"])
            snapshot = data.get_option_snapshot(OptionSnapshotRequest(
                symbol_or_symbols=event["contract"], feed=OptionsFeed.OPRA))[event["contract"]]
            planned_at = datetime.now(timezone.utc) if fixed_now is None else now
            plan = order_plan(event, account=account, broker_position=positions.get(event["contract"]),
                              snapshot=snapshot, contract=contract, now=planned_at)
        except (ValueError, KeyError, TypeError) as exc:
            result.append({"event_id": event["event_id"], "status": "blocked", "reason": str(exc)})
            continue
        if not submit:
            result.append({"event_id": event["event_id"], "status": "preview", "plan": plan})
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
        # A second action needs a fresh account/position/order reconciliation.
        break
    return result
