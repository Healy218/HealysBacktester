"""Read-only V6/Alpaca paper-account compatibility preflight.

No order-submission method is imported or called here. Existing V6 positions
are historical simulator positions, never instructions to open broker orders.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3


def read_v6_positions(database: Path, *, capital: float, sizing_source: str = "projection") -> dict:
    """Summarize active V6 simulator positions without modifying its database."""
    if not math.isfinite(capital) or capital <= 0:
        raise ValueError("capital must be positive and finite")
    if sizing_source not in ("projection", "paper_buying_power"):
        raise ValueError("unknown sizing source")
    database = Path(database)
    if not database.is_file() or database.is_symlink():
        raise ValueError("V6 portfolio must be an existing regular file")
    rows = []
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        equity_row = db.execute("SELECT value FROM metadata WHERE key='equity'").fetchone()
        if equity_row is None:
            raise ValueError("V6 portfolio lacks equity metadata")
        normalized_equity = float(equity_row[0])
        if not math.isfinite(normalized_equity) or normalized_equity <= 0:
            raise ValueError("V6 normalized equity is invalid")
        source = db.execute("SELECT key,symbol,state,payload FROM positions WHERE state!='closed' ORDER BY key").fetchall()
    for key, symbol, state, raw in source:
        position = json.loads(raw)
        fraction = float(position["initial_amount"] if sizing_source == "projection" else position["size_fraction"])
        price = float(position["entry_price"])
        if (not math.isfinite(fraction) or not 0 < fraction <= 1 or
                not math.isfinite(price) or price <= 0):
            raise ValueError(f"invalid V6 allocation or entry price for {key}")
        allocation = fraction * capital
        contract_cost = price * 100
        contracts = math.floor(allocation / contract_cost)
        rows.append({
            "key": key,
            "symbol": symbol,
            "state": state,
            "contract": position["contract"],
            "opened_at": position["opened_at"],
            "historical_only": True,
            "allocation_fraction": fraction,
            "allocation_usd": round(allocation, 2),
            "entry_contract_cost_usd": round(contract_cost, 2),
            "indicative_whole_contracts": contracts,
            "unallocated_usd": round(allocation - contracts * contract_cost, 2),
        })
    return {
        "source": "v6-simulator-read-only",
        "capital_usd": capital,
        "sizing_source": sizing_source,
        "normalized_equity": normalized_equity,
        "active_positions": len(rows),
        "zero_contract_positions": sum(row["indicative_whole_contracts"] == 0 for row in rows),
        "positions": rows,
        "limitation": "Historical V6 positions are sizing examples only; no retroactive broker orders.",
    }


def paper_account_snapshot(key: str, secret: str, *, contracts: tuple[str, ...] = ()) -> dict:
    """Query only paper account, positions, open orders and listed contracts."""
    if not key or not secret:
        raise ValueError("dedicated Alpaca paper API key and secret are required")
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    client = TradingClient(key, secret, paper=True)
    account = client.get_account()
    positions = client.get_all_positions()
    orders = client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=100))
    if len(contracts) > 5:
        raise ValueError("contract preflight is bounded to the five V6 slots")
    contract_checks = []
    for symbol in sorted(set(contracts)):
        try:
            contract = client.get_option_contract(symbol)
            status = str(getattr(contract.status, "value", contract.status))
            contract_checks.append({"symbol": symbol, "listed": True,
                "status": status, "tradable": bool(contract.tradable),
                "multiplier": str(contract.size)})
        except Exception as exc:
            contract_checks.append({"symbol": symbol, "listed": False,
                "error_type": type(exc).__name__})
    status = str(getattr(account.status, "value", account.status))
    options_level = account.options_trading_level
    try:
        level = int(options_level)
    except (TypeError, ValueError):
        level = None
    result = {
        "source": "alpaca-paper-read-only",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "account_fingerprint": hashlib.sha256(str(account.id).encode()).hexdigest(),
        "account_status": status,
        "trading_blocked": bool(account.trading_blocked or account.account_blocked),
        "options_trading_level": level,
        "options_approved_level": account.options_approved_level,
        "options_buying_power_usd": str(account.options_buying_power),
        "cash_usd": str(account.cash),
        "equity_usd": str(account.equity),
        "position_count": len(positions),
        "option_positions": [
            {"symbol": p.symbol, "qty": str(p.qty)}
            for p in positions if str(getattr(p.asset_class, "value", p.asset_class)) == "us_option"
        ],
        "open_order_count": len(orders),
        "open_orders_may_be_truncated": len(orders) == 100,
        "contract_checks": contract_checks,
        "open_orders": [
            {"symbol": o.symbol, "side": str(getattr(o.side, "value", o.side)),
             "status": str(getattr(o.status, "value", o.status)), "qty": str(o.qty)}
            for o in orders
        ],
        "long_option_entry_eligible": status.upper() == "ACTIVE" and not (account.trading_blocked or account.account_blocked) and level is not None and level >= 2,
    }
    return result
