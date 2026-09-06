"""Resumable capture of exact planned option windows; no outcome selection.

Preview by default. --run uses the existing Massive account, retains immutable
raw bundles, and materializes each fully covered symbol. Failures stop the run;
completed bundles can be verified and reused. No model is trained here.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import time

from nn_meta import option_tick_dataset as d
from options.data.massive_ticks import MassiveTicks, TickDataError, canonical_bytes
from scripts.capture_option_ticks import load_verified_capture
from scripts.prepare_option_tick_features import capture_plan
from scripts import materialize_v6_tick_store as streaming


def capture_one(batch, root, *, client=None, reserve_bytes=20*1024**3):
    key = d._hash(batch)
    parent = root / key
    parent.mkdir(parents=True, exist_ok=True)
    for attempt in sorted(parent.iterdir()):
        if not (attempt / "manifest.json").exists():
            continue
        report, _ = load_verified_capture(attempt)
        if any(report["plan"].get(k) != batch[k] for k in ("contracts", "start_ns", "end_ns")):
            raise TickDataError("retained capture differs from planned batch")
        return attempt
    if shutil.disk_usage(root).free < reserve_bytes:
        raise TickDataError("capture stopped at reserved free disk space; existing evidence retained")
    output = parent / f"attempt-{len(list(parent.iterdir())):04d}"
    output.mkdir(exist_ok=False)
    plan = {**batch, "contract_selection": "sealed pre-outcome v6 request inventory"}
    (output / "plan.json").write_bytes(canonical_bytes(plan) + b"\n")
    client = client or MassiveTicks()
    entries = []
    for contract in batch["contracts"]:
        entry = {"contract": contract, "captures": {}, "files": {}}
        for kind in ("quotes", "trades"):
            for retry in range(4):
                try:
                    rows, metadata = client.capture(contract, kind, batch["start_ns"], batch["end_ns"], max_pages=20)
                    break
                except TickDataError as exc:
                    if retry == 3 or not any(s in str(exc) for s in ("transport failed", "HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504")):
                        raise
                    time.sleep(2**retry)
            data = gzip.compress(canonical_bytes(rows), mtime=0)
            name = f"{contract}.{kind}.json.gz"
            (output / name).write_bytes(data)
            entry["captures"][kind] = metadata
            entry["files"][name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            del rows, data
        entries.append(entry)
    report = {"complete": True, "plan": plan, "contracts": entries, "model_admission": False}
    (output / "manifest.json").write_bytes(canonical_bytes(report) + b"\n")
    load_verified_capture(output)
    return output


def prepare_symbol(inventory, policy_path, output):
    source = output / "streaming-source.txt"
    output.mkdir(parents=True, exist_ok=True)
    if source.exists() and source.read_bytes() != Path(streaming.__file__).read_bytes():
        raise TickDataError("streaming source changed; use a new task root")
    if not source.exists():
        source.write_bytes(Path(streaming.__file__).read_bytes())
    manifest = json.loads((inventory / "manifest.json").read_bytes())
    if manifest.get("complete") is not True:
        raise TickDataError("symbol inventory is incomplete")
    for name, digest in manifest["files_sha256"].items():
        if name not in ("requests.json", "selection_provenance.json", "root_aliases.json") or d._file_hash(inventory / name) != digest:
            raise TickDataError("symbol inventory files changed")
    provenance = json.loads((inventory / "selection_provenance.json").read_bytes())
    for path, digest in {**provenance["source_sha256"], **provenance["input_files_sha256"]}.items():
        if d._file_hash(path) != digest:
            raise TickDataError("selection source or input changed since inventory computation")
    requests = json.loads((inventory / "requests.json").read_bytes())
    policy = json.loads(policy_path.read_bytes())
    task = d.create_task_manifest(requests, selection_reference_paths=[
        inventory / "requests.json", inventory / "selection_provenance.json",
        inventory / "root_aliases.json", inventory / "manifest.json", policy_path, source],
        feature_policy=policy, root_aliases=json.loads((inventory / "root_aliases.json").read_bytes()),
        allow_empty=not requests)
    # Bound raw bundle memory even for heavily quoted contracts.
    plan = capture_plan(task, max_span_ns=15*60*1_000_000_000)
    for name, value in (("task.json", task), ("capture_plan.json", plan)):
        path = output / name
        data = canonical_bytes(value) + b"\n"
        if path.exists() and path.read_bytes() != data:
            raise TickDataError("prepared task or plan changed")
        if not path.exists():
            path.write_bytes(data)
    return task, plan


def run(args):
    inventory, output, policy = d._path(args.inventory), d._path(args.output), d._path(args.policy)
    scope = json.loads((inventory / "scope.json").read_bytes())
    symbols = args.symbols.split(",") if args.symbols else scope["symbols"]
    if not symbols or len(set(symbols)) != len(symbols) or set(symbols) - set(scope["symbols"]):
        raise TickDataError("capture symbols must belong to the sealed inventory")
    if not args.run:
        print(json.dumps({"symbols": symbols, "workers": args.workers,
                          "downloads_started": False, "output": str(output)}))
        return
    from dotenv import load_dotenv
    load_dotenv()
    output.mkdir(parents=True, exist_ok=True)
    source_hash = d._file_hash(Path(__file__))
    run_scope = {"inventory_scope_sha256": d._file_hash(inventory / "scope.json"),
        "policy_sha256": d._file_hash(policy), "symbols": symbols, "capture_source_sha256": source_hash}
    path = output / "scope.json"
    if path.exists() and json.loads(path.read_bytes()) != run_scope:
        raise TickDataError("capture run scope changed")
    if not path.exists():
        path.write_bytes(canonical_bytes(run_scope) + b"\n")
    stores = {}
    for symbol in symbols:
        symbol_inventory = inventory / symbol
        while not (symbol_inventory / "manifest.json").exists():
            if not args.wait_for_inventory:
                raise TickDataError(f"{symbol} request inventory is not complete")
            print(json.dumps({"waiting_for_inventory": symbol}), flush=True)
            time.sleep(30)
        task, plan = prepare_symbol(symbol_inventory, policy, output / "prepared" / symbol)
        store = output / "stores" / symbol
        if store.exists():
            manifest = json.loads((store / "manifest.json").read_bytes())
            d.load_feature_store(store, expected_task_sha256=task["task_sha256"],
                                 expected_store_sha256=manifest["store_sha256"])
        else:
            raw = output / "captures" / symbol
            raw.mkdir(parents=True, exist_ok=True)
            captures = []
            print(json.dumps({"symbol": symbol, "distinct_requests": len(task["requests"]),
                              "capture_batches": len(plan["capture_batches"])}), flush=True)
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = [executor.submit(capture_one, batch, raw) for batch in plan["capture_batches"]]
                try:
                    for future in as_completed(futures):
                        captures.append(future.result())
                        if len(captures) % 100 == 0:
                            print(json.dumps({"symbol": symbol, "captured_batches": len(captures)}), flush=True)
                except BaseException:
                    for future in futures:
                        future.cancel()
                    raise
            manifest = streaming.materialize(task, sorted(captures), store)
            d.load_feature_store(store, expected_task_sha256=task["task_sha256"],
                                 expected_store_sha256=manifest["store_sha256"])
        stores[symbol] = {"directory": str(store), "task_sha256": task["task_sha256"],
                          "store_sha256": manifest["store_sha256"]}
        print(json.dumps({"symbol": symbol, "store_complete": True, "rows": manifest["row_count"]}), flush=True)
    if d._file_hash(Path(__file__)) != source_hash:
        raise TickDataError("capture runner changed during execution")
    report = {"complete": True, "stores": stores, "freeze_started": False}
    target = output / "manifest.json"
    if target.exists() and json.loads(target.read_bytes()) != report:
        raise TickDataError("completed capture run changed")
    if not target.exists():
        target.write_bytes(canonical_bytes(report) + b"\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inventory", type=Path, required=True)
    ap.add_argument("--policy", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--symbols")
    ap.add_argument("--workers", type=int, choices=range(1, 33), default=8)
    ap.add_argument("--wait-for-inventory", action="store_true")
    ap.add_argument("--run", action="store_true")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
