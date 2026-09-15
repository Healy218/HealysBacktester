"""Write a draft full-variant inventory; never starts capture/build/training."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nn_meta.multitimeframe_catalog import registered_catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-scope", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.parent_scope.read_bytes()
    scope = json.loads(raw)
    if scope.get("schema") != "v6-short-dte-campaign-v1":
        raise ValueError("Expected the existing short-DTE scope as symbol/date reference")
    spec_path = Path(scope["parent_spec"])
    spec_raw = spec_path.read_bytes()
    spec_sha = sha256(spec_raw).hexdigest()
    if scope["anchors"].get(str(spec_path)) != spec_sha:
        raise ValueError("Parent training dates are not backed by the scope's baseline hash")
    spec = json.loads(spec_raw)
    catalog = registered_catalog(scope["symbols"])
    result = {
        "parent_scope_sha256": sha256(raw).hexdigest(),
        "parent_spec_sha256": spec_sha,
        "train_window": spec["train_window"],
        "historical_window": scope["design"]["historical_window"],
        "date_policy": "Preserve existing train/evaluation dates; previously inspected revalidation",
        "catalog": catalog,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Refuse to overwrite even a draft without a new explicit output identity.
    with args.output.open("x") as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write("\n")
    print(json.dumps({k: v for k, v in catalog.items() if k not in ("records", "symbols")}, indent=2))


if __name__ == "__main__":
    main()
