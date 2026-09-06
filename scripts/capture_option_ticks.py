"""Preview or execute a small, explicit Massive quotes/trades capture.

Example: python -m scripts.capture_option_ticks --contract SPY260824C00700000
  --start 2026-08-24T13:30:00Z --end 2026-08-24T13:45:00Z
  --output nn_meta/option_tick_captures/pilot --run

Select contracts using information available before the window. This utility
does not imply that its manually selected pilot is a model training universe.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

import pandas as pd

from options.data.massive_ticks import MassiveTicks, TickDataError, canonical_bytes, verify_capture
from options.data.provider import parse_occ_symbol
from options.tick_features import verified_window_features


def implementation_hashes():
    root = Path(__file__).resolve().parents[1]
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in (
        "options/data/massive_ticks.py", "options/tick_features.py", "scripts/capture_option_ticks.py")}


def load_verified_capture(directory):
    """Load an existing immutable bundle; verify files, rows, bounds and contracts.

    This deliberately supports older raw capture manifests without current
    feature-policy hashes, so retained ticks can be re-evaluated offline while
    preserving the original capture/feature report. It never trusts stored
    feature values as validation of raw capture completeness.
    """
    directory = Path(directory)
    try:
        report = json.loads((directory / "manifest.json").read_text())
        plan = report["plan"]
        contracts = plan["contracts"]
        entries = report["contracts"]
        if (report.get("complete") is not True or not isinstance(contracts, list)
                or not 1 <= len(contracts) <= 10 or len(set(contracts)) != len(contracts)
                or not isinstance(entries, list) or len(entries) != len(contracts)
                or {entry["contract"] for entry in entries} != set(contracts)):
            raise TickDataError("capture bundle contract set or completeness mismatch")
        result = {}
        for entry in entries:
            contract = entry["contract"]
            parse_occ_symbol(contract)
            result[contract] = {}
            for kind in ("quotes", "trades"):
                name = f"{contract}.{kind}.json.gz"
                path = directory / name
                if path.is_symlink():
                    raise TickDataError("capture data file must not be a symlink")
                data = path.read_bytes()
                declared = entry["files"][name]
                if len(data) != declared["bytes"] or hashlib.sha256(data).hexdigest() != declared["sha256"]:
                    raise TickDataError("capture compressed file size or SHA256 mismatch")
                rows = json.loads(gzip.decompress(data))
                verify_capture(rows, entry["captures"][kind], contract=contract, kind=kind,
                               start_ns=plan["start_ns"], end_ns=plan["end_ns"])
                result[contract][kind] = rows
        return report, result
    except TickDataError:
        raise
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise TickDataError("invalid or incomplete capture bundle") from exc


def timestamp_ns(value):
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tz is None:
        raise TickDataError("capture timestamps require an explicit timezone")
    return int(stamp.value)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--contract", action="append", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--max-pages", type=int, default=20)
    ap.add_argument("--allow-unconditioned-trades", action="store_true",
                    help="explicitly permit quote-test signing of trades with missing/empty conditions")
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args()
    contracts = sorted({c.upper().removeprefix("O:") for c in args.contract})
    for c in contracts:
        parse_occ_symbol(c)
    start, end = timestamp_ns(args.start), timestamp_ns(args.end)
    if not 0 < end - start <= 86_400_000_000_000 or not 1 <= len(contracts) <= 10:
        ap.error("pilot requires 1–10 explicit contracts and a window of at most one day")
    if args.output.exists() or any(p.is_symlink() for p in (args.output, *args.output.parents)):
        ap.error("output must be a new path without symlink components")
    if not 1 <= args.max_pages <= 1000:
        ap.error("max-pages must be between 1 and 1000")
    plan = {"contracts": contracts, "start_ns": start, "end_ns": end,
            "max_pages_per_kind_contract": args.max_pages,
            "contract_selection": "explicit pilot; no training-universe admission",
            "output": str(args.output), "execute": args.run}
    feature_policy = {"availability": "historical_sip_timestamp", "max_quote_age_ns": 30_000_000_000,
                      "allowed_trade_conditions": [], "condition_namespace": "massive_integer",
                      "allow_unconditioned_trades": args.allow_unconditioned_trades,
                      "cross_stream_ties": "exclude_from_quote_test_signing",
                      "model_admission": False}
    source_hashes = implementation_hashes()
    plan["feature_policy"] = feature_policy
    if not args.run:
        print(json.dumps(plan, indent=2))
        return
    from dotenv import load_dotenv
    load_dotenv()
    client = MassiveTicks()
    args.output.mkdir(parents=True)
    (args.output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    reports, begun = [], time.monotonic()
    for contract in contracts:
        captured, manifests, files = {}, {}, {}
        for kind in ("quotes", "trades"):
            ticks, manifest = client.capture(contract, kind, start, end, max_pages=args.max_pages)
            data = gzip.compress(canonical_bytes(ticks), mtime=0)
            name = f"{contract}.{kind}.json.gz"
            (args.output / name).write_bytes(data)
            files[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            captured[kind], manifests[kind] = ticks, manifest
            print(json.dumps({"contract": contract, "kind": kind, "records": len(ticks),
                              "pages": manifest["pages"], "compressed_bytes": len(data)}), flush=True)
        features = verified_window_features(captured["quotes"], captured["trades"],
            quote_manifest=manifests["quotes"], trade_manifest=manifests["trades"],
            contract=contract, start_ns=start, end_ns=end,
            max_quote_age_ns=feature_policy["max_quote_age_ns"],
            allowed_trade_conditions=feature_policy["allowed_trade_conditions"],
            allow_unconditioned_trades=feature_policy["allow_unconditioned_trades"])
        reports.append({"contract": contract, "captures": manifests, "files": files, "features": features})
    if source_hashes != implementation_hashes():
        raise TickDataError("capture/feature implementation changed during capture; no complete manifest written")
    report = {"plan": plan, "complete": True, "elapsed_seconds": time.monotonic() - begun,
              "contracts": reports, "model_admission": False,
              "implementation_sha256": source_hashes, "feature_policy": feature_policy}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"complete": True, "manifest": str(args.output / "manifest.json"),
                      "elapsed_seconds": report["elapsed_seconds"]}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except TickDataError as exc:
        raise SystemExit(str(exc)) from None
