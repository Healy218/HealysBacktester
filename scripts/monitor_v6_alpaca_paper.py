"""Read the fresh Alpaca paper account without consulting the V6 simulator."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import dotenv_values

from integrations.alpaca_paper.v6_preflight import paper_account_snapshot

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--state", type=Path, help="Optional fresh paper runtime health")
    args = parser.parse_args()
    secrets = dotenv_values(args.env)
    key = secrets.get("ALPACA_PAPER_API_KEY")
    secret = secrets.get("ALPACA_PAPER_API_SECRET")
    if not key or not secret:
        parser.error("dedicated Alpaca paper credentials are missing")
    account = paper_account_snapshot(key, secret)
    report = {"schema": "v6-alpaca-paper-monitor-v1",
              "monitor_can_submit_orders": False, "alpaca": account}
    if args.state:
        manifest = json.loads((args.state / 'paper-restart.json').read_text())
        report['broker_orders_enabled'] = bool(manifest.get('order_submission_enabled'))
        report['scanner_enabled'] = bool(manifest.get('scanner_enabled'))
        status_path = args.state / 'broker-status.json'
        report['runtime'] = json.loads(status_path.read_text()) if status_path.exists() else None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    temporary.replace(args.output)
    print(json.dumps({"observed_at": account["observed_at"],
                      "broker_positions": account["position_count"],
                      "broker_open_orders": account["open_order_count"],
                      "long_option_entry_eligible": account["long_option_entry_eligible"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
