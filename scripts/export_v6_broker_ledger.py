"""Export a broker-style $10,000 V6 paper ledger from the research ledger.

The live V6 portfolio stores normalized equity and remains research-only. This
projection scales those immutable allocations to a stated starting capital,
realizes closed-leg P/L, and marks open positions from fresh midpoint quotes.
It never writes to the live portfolio database.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from nn_meta.live.v6_market import MassiveMarket, utcnow

COST = 0.0015
ROOT = Path(__file__).resolve().parents[1]


def iso_stamp(value):
    """Return a timezone-qualified ISO timestamp for the dashboard contract."""
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def export(args):
    load_dotenv(args.env)
    now = utcnow()
    market = MassiveMarket(args.state / "market")
    rows = []
    with sqlite3.connect(f"file:{args.database}?mode=ro", uri=True) as db:
        positions = db.execute(
            "SELECT key,state,payload FROM positions ORDER BY key"
        ).fetchall()
        normalized_equity = float(
            db.execute("SELECT value FROM metadata WHERE key='equity'").fetchone()[0]
        )

    for key, state, raw in positions:
        position = json.loads(raw)
        initial_amount = float(position["initial_amount"])
        entry_price = float(position["entry_price"])
        entry_notional = initial_amount * args.capital
        factor = float(position.get("return_factor", 1.0))
        realized = entry_notional * (factor - 1.0) if state == "closed" else 0.0
        mark = None
        quote = None
        unrealized = 0.0
        if state != "closed":
            try:
                # Give the provider a small receipt window; the quote itself
                # is still checked for freshness by MassiveMarket.
                quote = market.execution_quote(position["contract"], after=now - timedelta(seconds=45))
                midpoint = (float(quote["bid"]) + float(quote["ask"])) / 2.0
                mark = midpoint * (1.0 - COST)
                unrealized = entry_notional * (mark / entry_price - 1.0)
            except Exception as exc:  # preserve missing mark rather than invent 0
                quote = {"error": f"{type(exc).__name__}: {exc}"}
        rows.append({
            "key": key,
            "state": state,
            "symbol": position["symbol"],
            "strategy": position["strategy"],
            "contract": position["contract"],
            "entry_ts": iso_stamp(position["entry_ts"]),
            "opened_at": position["opened_at"],
            "entry_price_net": entry_price,
            "allocation_usd": entry_notional,
            "return_factor": factor,
            "realized_pnl_usd": realized,
            "mark_price_net": mark,
            "unrealized_pnl_usd": unrealized if mark is not None else None,
            "quote_received_at": quote.get("received_at") if quote else None,
            "quote_bid": quote.get("bid") if quote else None,
            "quote_ask": quote.get("ask") if quote else None,
            "closed_at": position.get("trigger_at"),
            "exit_reason": position.get("trigger_reason"),
        })

    realized = sum(row["realized_pnl_usd"] for row in rows)
    unrealized_values = [row["unrealized_pnl_usd"] for row in rows if row["unrealized_pnl_usd"] is not None]
    unrealized = sum(unrealized_values)
    open_count = sum(row["state"] != "closed" for row in rows)
    complete_mark = len(unrealized_values) == open_count
    summary = {
        "schema": "v6-broker-ledger-v1",
        "starting_capital_usd": args.capital,
        "snapshot_at": now.isoformat(),
        "source_database": str(args.database),
        "source_normalized_equity": normalized_equity,
        "closed_trades": sum(row["state"] == "closed" for row in rows),
        "open_trades": sum(row["state"] != "closed" for row in rows),
        "realized_pnl_usd": realized,
        "marked_open_trades": len(unrealized_values),
        "unmarked_open_trades": open_count - len(unrealized_values),
        "complete_open_mark": complete_mark,
        "unrealized_pnl_usd_marked": unrealized,
        "total_pnl_usd_marked": realized + unrealized,
        "equity_usd_marked": args.capital + realized + unrealized,
        "unrealized_pnl_usd": unrealized if complete_mark else None,
        "total_pnl_usd": realized + unrealized if complete_mark else None,
        "equity_usd": args.capital + realized + unrealized if complete_mark else None,
        "pricing": "entry midpoint plus 0.15% cost; open marks midpoint minus 0.15% cost",
        "broker_orders": False,
        "research_ledger_unchanged": True,
    }
    document = {"schema": "v6-broker-ledger-v1", "summary": summary, "trades": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # The dashboard reads this file while the exporter runs. Publish each
    # complete snapshot in one rename so it never sees truncated JSON.
    with tempfile.NamedTemporaryFile("w", dir=args.output.parent, prefix=".v6-broker-",
                                     suffix=".json", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            json.dump(document, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary.chmod(0o600)
            temporary.replace(args.output)
        finally:
            temporary.unlink(missing_ok=True)
    csv_output = args.output.with_suffix(".csv")
    with tempfile.NamedTemporaryFile("w", newline="", dir=csv_output.parent,
                                     prefix=".v6-broker-", suffix=".csv", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else [])
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
            temporary.chmod(0o600)
            temporary.replace(csv_output)
        finally:
            temporary.unlink(missing_ok=True)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--capital", type=float, default=10_000.0)
    export(parser.parse_args())
