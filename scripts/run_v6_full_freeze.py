"""Capture full planned ticks, seal final inputs, then execute the full freeze.

The user's approved local-research scope is preserved. This supervisor never
marks a download or queued launcher as a started/completed baseline freeze.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

from nn_meta import config
from nn_meta.v6_expansion import ExpandedInputs, from_environment, sha256
from scripts.plan_v6_option_requests import _config_record, _source_hashes, _require_expanded
from scripts.run_v6_tick_capture import run as capture


def seal(planning, inventory, tick_output):
    inventory_scope = json.loads((inventory / "scope.json").read_bytes())
    inventory_report = json.loads((inventory / "manifest.json").read_bytes())
    captured = json.loads((tick_output / "manifest.json").read_bytes())
    symbols = set(config.UNDERLYINGS)
    if (inventory_scope["config"] != _config_record()
            or inventory_scope["source_sha256"] != _source_hashes()
            or inventory_report.get("complete") is not True or captured.get("complete") is not True
            or set(inventory_report["symbols"]) != symbols
            or set(captured["stores"]) != symbols or set(planning.document["symbols"]) != symbols):
        raise ValueError("full freeze requires unchanged full-universe inventory and tick stores")
    planning.assert_unchanged()
    doc = json.loads(planning.path.read_bytes())
    for symbol, entry in doc["symbols"].items():
        for name in ("timeframe_flags", "vwap_observations"):
            if entry.get(name) is not None:
                entry[name]["path"] = str(planning.reference(entry[name]))
        entry["tick_store"] = captured["stores"][symbol]
    doc["context_references"] = [{"path": str(planning.reference(ref)), "sha256": ref["sha256"]}
                                 for ref in doc.get("context_references", [])]
    for path in (planning.path, inventory / "scope.json", inventory / "manifest.json", tick_output / "manifest.json"):
        doc["context_references"].append({"path": str(path.absolute()), "sha256": sha256(path)})
    final = tick_output / "final-inputs.json"
    data = json.dumps(doc, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if final.exists() and final.read_text() != data:
        raise ValueError("final input manifest changed; do not reuse this campaign")
    if not final.exists():
        with final.open("x") as stream:
            stream.write(data)
    digest = sha256(final)
    ExpandedInputs(final, digest, parity_policy=config.V6_PARITY_POLICY)
    anchor = tick_output / "final-inputs.sha256"
    if anchor.exists() and anchor.read_text().strip() != digest:
        raise ValueError("final input anchor changed")
    if not anchor.exists():
        anchor.write_text(digest + "\n")
    return final, digest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inventory", type=Path, required=True)
    ap.add_argument("--policy", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--workers", type=int, choices=range(1, 33), default=8)
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args()
    _require_expanded()
    planning = from_environment()
    if not config.DATA_CANDIDATE:
        raise ValueError("full freeze requires the repaired candidate")
    if not args.run:
        print(json.dumps({"symbols": len(config.UNDERLYINGS), "strategies": len(config.PROPOSAL_STRATEGIES),
                          "capture_workers": args.workers, "run": False, "freeze_started": False}))
        return
    output, inventory = args.output.absolute(), args.inventory.absolute()
    capture(SimpleNamespace(inventory=inventory, policy=args.policy.absolute(), output=output,
        symbols=None, workers=args.workers, wait_for_inventory=True, run=True))
    final, digest = seal(planning, inventory, output)
    environment = dict(os.environ, NN_META_V6_INPUTS=str(final), NN_META_V6_INPUTS_SHA256=digest)
    print(json.dumps({"stage": "launching_full_freeze", "inputs": str(final), "sha256": digest}), flush=True)
    # The existing launcher performs full candidate/source/coverage checks and
    # records the real freeze-worker start in its own output and campaign log.
    result = subprocess.run(["bash", "scripts/run_freeze_v6_local.sh", "--run"], env=environment)
    (output / "freeze-launcher-result.json").write_text(json.dumps({
        "returncode": result.returncode, "freeze_completed": result.returncode == 0}, indent=2) + "\n")
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
