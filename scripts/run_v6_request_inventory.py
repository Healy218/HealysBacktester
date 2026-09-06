"""Run the full pre-outcome inventory in bounded, resumable symbol processes.

Each completed symbol retains the planner's immutable selection/source/input
evidence. No option outcomes or ticks are fetched. Resume rechecks provenance.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys

from nn_meta import config
from nn_meta.v6_expansion import from_environment, sha256
from scripts.plan_v6_option_requests import _config_record, _source_hashes, _require_expanded


def verified_result(directory, sources, configuration):
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if manifest.get("complete") is not True:
        raise ValueError("incomplete symbol inventory")
    for name, digest in manifest["files_sha256"].items():
        if name not in ("requests.json", "selection_provenance.json", "root_aliases.json"):
            raise ValueError("unexpected inventory file")
        if sha256(directory / name) != digest:
            raise ValueError("inventory bytes changed")
    provenance = json.loads((directory / "selection_provenance.json").read_bytes())
    if provenance["source_sha256"] != sources or provenance["config"] != configuration:
        raise ValueError("inventory source/config changed; use a new output root")
    for path, digest in provenance["input_files_sha256"].items():
        if sha256(path) != digest:
            raise ValueError("inventory input bytes changed")
    return {"requests": manifest["request_count"], "selected": provenance["selected_count"],
            "manifest_sha256": sha256(directory / "manifest.json")}


def run(args):
    _require_expanded()
    expanded = from_environment()
    symbols = list(config.UNDERLYINGS)
    if set(symbols) != set(expanded.document["symbols"]):
        raise ValueError("full inventory requires context for exactly the configured universe")
    output = args.output.absolute()
    if any(p.is_symlink() for p in (output, *output.parents)) or output.is_relative_to(config.DATA_CACHE.absolute()):
        raise ValueError("inventory output must be outside sealed cache without symlinks")
    sources, configuration = _source_hashes(), _config_record()
    scope = {"schema": "v6-full-request-inventory-v1", "config": configuration,
             "symbols": symbols, "source_sha256": sources}
    if not args.run:
        print(json.dumps({"symbols": len(symbols), "workers": args.workers, "output": str(output),
                          "run": False, "downloads_started": False}))
        return
    output.mkdir(parents=True, exist_ok=True)
    scope_path = output / "scope.json"
    if scope_path.exists():
        if json.loads(scope_path.read_bytes()) != scope:
            raise ValueError("existing inventory belongs to a different scope")
    else:
        with scope_path.open("x") as stream:
            json.dump(scope, stream, sort_keys=True)
    (output / "logs").mkdir(exist_ok=True)
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1",
                       OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMBA_NUM_THREADS="1")

    def one(symbol):
        directory = output / symbol
        if not directory.exists():
            with (output / "logs" / f"{symbol}.log").open("a") as log:
                result = subprocess.run([sys.executable, "-m", "scripts.plan_v6_option_requests",
                    "--symbols", symbol, "--output", str(directory), "--run"],
                    env=environment, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(f"{symbol} planner failed ({result.returncode}); see {log.name}")
        record = verified_result(directory, sources, configuration)
        print(json.dumps({"symbol": symbol, **record}), flush=True)
        return symbol, record

    results = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(one, symbol) for symbol in symbols]
        try:
            for future in as_completed(futures):
                symbol, record = future.result()
                results[symbol] = record
        except BaseException:
            for future in futures:
                future.cancel()
            raise
    if _source_hashes() != sources or _config_record() != configuration:
        raise ValueError("inventory source/config changed while running")
    expanded.assert_unchanged()
    report = {"schema": scope["schema"], "complete": True, "symbols": results,
              "request_count": sum(r["requests"] for r in results.values()),
              "selected_count": sum(r["selected"] for r in results.values()),
              "downloads_started": False, "freeze_started": False}
    target = output / "manifest.json"
    if target.exists() and json.loads(target.read_bytes()) != report:
        raise ValueError("completed inventory report changed")
    if not target.exists():
        with target.open("x") as stream:
            json.dump(report, stream, sort_keys=True, indent=2)
    print(json.dumps({"complete": True, "request_count": report["request_count"],
                      "selected_count": report["selected_count"]}), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--workers", type=int, choices=range(1, 5), default=2)
    ap.add_argument("--run", action="store_true")
    run(ap.parse_args())


if __name__ == "__main__":
    main()
