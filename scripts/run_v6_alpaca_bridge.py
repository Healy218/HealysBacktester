#!/usr/bin/env python3
"""Preview future V6 structured events against Alpaca paper; guarded submit opt-in."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path

from dotenv import dotenv_values

from integrations.alpaca_paper.v6_bridge import Journal, events_from_fresh_state, process_events, stamp

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--submit", action="store_true", help="Submit to Alpaca PAPER after manifest opt-in")
    args = parser.parse_args()
    state = args.state.resolve()
    manifest = json.loads((state / "paper-restart.json").read_text())
    if (manifest.get("schema") != "v6-alpaca-paper-restart-prepared-v1" or
            manifest.get("historical_positions_imported") is not False or
            not manifest.get("account_fingerprint")):
        parser.error("fresh V6 paper state manifest is invalid")
    if args.submit and (manifest.get("order_submission_enabled") is not True or
                        manifest.get("scanner_enabled") is not True):
        parser.error("paper submission requires an activated scanner and order manifest")
    secrets = dotenv_values(args.env)
    key, secret = secrets.get("ALPACA_PAPER_API_KEY"), secrets.get("ALPACA_PAPER_API_SECRET")
    if not key or not secret:
        parser.error("dedicated paper credentials are missing")
    from alpaca.data.historical.option import OptionHistoricalDataClient
    from alpaca.trading.client import TradingClient
    trading = TradingClient(key, secret, paper=True)
    data = OptionHistoricalDataClient(key, secret)
    lock_path = state / "bridge.lock"
    with lock_path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        journal = Journal(state / "broker-orders.sqlite3")
        database = state / "portfolio.sqlite3"
        if not database.exists():
            events = []
        else:
            events = events_from_fresh_state(database, activated_at=stamp(manifest["prepared_at"]))
        outcome = process_events(events, journal=journal, trading=trading, data=data,
                                 expected_fingerprint=manifest["account_fingerprint"],
                                 submit=args.submit, now=datetime.now(timezone.utc))
    print(json.dumps({"schema": "v6-alpaca-bridge-poll-v1", "mode": "submit" if args.submit else "preview",
                      "observed_events": len(events), "outcomes": outcome}, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
