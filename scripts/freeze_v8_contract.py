# scripts/freeze_v8_contract.py — V8.0-contract: pin every stage-0 artifact.
"""Write docs/specs/V8_CONTRACT_20261008.json: path, sha256 and size of each
stage-0 artifact plus the coverage summary, so stage-1 runs can prove they
read exactly the frozen universe, bars, admission rule and costs.

    ./venv/bin/python scripts/freeze_v8_contract.py           # write (refuses overwrite)
    ./venv/bin/python scripts/freeze_v8_contract.py --verify  # check current files

nn_meta.v8_contract.verify() is the same check for stage-1 code.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nn_meta import v8_contract as vc  # noqa: E402

ARTIFACTS = {
    "pool": "docs/specs/V8_POOL_PIT2021_20261007.json",
    "liquidity_rule": "docs/specs/V8_LIQUIDITY_20261008.json",
    "cost_table": "docs/specs/V8_COSTS_20261008.json",
    "pit_report": "nn_meta/validation/v8-pit-20261007-r0/report.json",
    "pit_membership": "nn_meta/validation/v8-pit-20261007-r0/membership.parquet",
    "bars_1h": "nn_meta/validation/v8-data-20261008-r0/bars_1h.parquet",
    "bars_1d": "nn_meta/validation/v8-data-20261008-r0/bars_1d.parquet",
    "coverage": "nn_meta/validation/v8-data-20261008-r0/coverage.parquet",
    "bar_spans": "nn_meta/validation/v8-data-20261008-r0/spans.json",
    "events": "nn_meta/validation/v8-data-20261008-r0/events.json",
    "admission": "nn_meta/validation/v8-liquidity-20261008-r0/admission.parquet",
    "stock_quotes": "nn_meta/validation/v8-spreads-stock-20261008-r0/quotes.parquet",
    "option_spreads": "nn_meta/validation/v8-spreads-option-20261008-r0/model.json",
}
CODE = ["nn_meta/universe_pit.py", "nn_meta/v8_fills.py", "nn_meta/v8_parallel.py",
        "scripts/build_v8_universe_pit.py", "scripts/freeze_v8_pool.py",
        "scripts/build_v8_bars.py", "scripts/sample_v8_stock_spreads.py",
        "scripts/build_v8_option_spreads.py", "scripts/build_v8_admission.py",
        "scripts/build_v8_cost_table.py"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        vc.verify()
        print(f"contract OK: {vc.CONTRACT.relative_to(REPO)}")
        return
    if vc.CONTRACT.exists():
        raise SystemExit(f"{vc.CONTRACT} exists; contracts are write-once")
    adm = json.loads((REPO / "nn_meta/validation/v8-liquidity-20261008-r0/summary.json").read_text())
    cov = json.loads((REPO / "nn_meta/validation/v8-data-20261008-r0/coverage_summary.json").read_text())
    status = {k: sum(v.get(k, 0) for v in cov.values())
              for k in ("needed_days", "ok", "partial", "missing", "delisted", "prelisting")}
    payload = {
        "schema": "v8-contract-v1",
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stage": "V8.0 universe and cost contract",
        "window": {"bars": ["2021-01-04", "2026-09-14"],
                   "first_admitted_day": adm["first_admitted_day"],
                   "development_end": "2025-12-31",
                   "holdout": "2026-01-01 onward (stage 5; not used in stage 1)"},
        "universe": {"symbols": len(cov), "tech_and_etfs": "162 tech (incl. delisted) + 17 ETFs"},
        "coverage": status,
        "admission": {k: adm[k] for k in ("admitted_share", "admitted_per_day", "rejections")},
        "consumer_rules": [
            "Trade only admitted (ticker, date) rows of the admission panel.",
            "No entries before 10:00 ET.",
            "Never compute a return across an events.json break or a non-ok bar day.",
            "Price every fill with nn_meta.v8_fills at cost_mult 1.0 and 1.5; midpoint-only results never count.",
            "Use adjusted prices for returns and raw prices for fills/costs.",
        ],
        "artifacts": {k: vc.describe(REPO / p) for k, p in ARTIFACTS.items()},
        "code": {p: vc.describe(REPO / p) for p in CODE},
    }
    vc.CONTRACT.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"wrote {vc.CONTRACT}")


if __name__ == "__main__":
    main()
