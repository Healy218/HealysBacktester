"""Preview V6 whole-contract fit; optionally inspect a dedicated Alpaca paper account.

This command only reads V6 state and uses Alpaca GET endpoints. It cannot
submit, replace, or cancel an order.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
import os
from pathlib import Path

from dotenv import dotenv_values

from integrations.alpaca_paper.v6_preflight import paper_account_snapshot, read_v6_positions

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v6-portfolio", type=Path, required=True)
    parser.add_argument("--capital", type=float, help="Offline projection base; defaults to $10,000")
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--account", action="store_true", help="Read the separate Alpaca paper account")
    parser.add_argument("--output", type=Path, help="Optional local JSON report")
    args = parser.parse_args()
    report = {"schema": "v6-alpaca-paper-preflight-v1", "order_submission_enabled": False}
    local = read_v6_positions(args.v6_portfolio, capital=10_000)
    if args.account:
        if args.capital is not None:
            parser.error("--account uses actual options buying power; omit --capital")
        secrets = dotenv_values(args.env)
        key, secret = secrets.get("ALPACA_PAPER_API_KEY"), secrets.get("ALPACA_PAPER_API_SECRET")
        if not key or not secret:
            parser.error("set ALPACA_PAPER_API_KEY and ALPACA_PAPER_API_SECRET in .env; do not reuse ALPACA_API_KEY")
        report["alpaca"] = paper_account_snapshot(key, secret,
            contracts=tuple(p["contract"] for p in local["positions"]))
        base = float(Decimal(report["alpaca"]["options_buying_power_usd"]))
        sizing_source = "paper_buying_power"
    else:
        report["alpaca"] = {"status": "not_checked", "reason": "dedicated paper credentials not yet supplied"}
        base = args.capital if args.capital is not None else 10_000
        sizing_source = "projection"
    report["v6"] = (local if sizing_source == "projection" and base == 10_000 else
        read_v6_positions(args.v6_portfolio, capital=base, sizing_source=sizing_source))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
