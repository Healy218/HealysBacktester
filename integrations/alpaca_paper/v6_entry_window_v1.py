"""Ten-minute PAPER entry admission; v2 eligibility and quote checks preserved."""
from datetime import datetime
from decimal import Decimal
from integrations.alpaca_paper.v6_bridge import client_id, quote_dict, stamp
from integrations.alpaca_paper.v6_pricing import entry_preview
from integrations.alpaca_paper.v6_pricing_v2 import POLICY, execution_limit

ENTRY_WINDOW_SECONDS = 600
ENTRY_WINDOW_POLICY = 'signal-close-ten-minute-v1'

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
        if not 0 <= (now - stamp(event.get("signal_close", event["at"]))).total_seconds() <= ENTRY_WINDOW_SECONDS:
            raise ValueError("entry event missed the ten-minute broker window")
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
