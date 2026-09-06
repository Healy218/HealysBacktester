"""Remote-safe preflight for a V4 evaluation environment.

Run this on the machine that holds v31 before starting an ablation.  It only
reads local files and imports optional dependencies; it does not call a market
provider or mutate artifacts.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pandas as pd

from nn_meta import config
from nn_meta.build_meta_dataset import V4_META_FEATURES
from nn_meta.feature_contract import CONTRACT_VERSION, assert_decision_safe
from nn_meta.mark_stream import mark_stream_path, option_b_blockers


def check_environment(dataset: Path, spec_path: Path, *, require_gbt: bool) -> dict:
    checks: dict[str, object] = {"ok": True, "pool": config.POOL,
                                 "interval": config.INTERVAL, "checks": []}

    def add(name: str, ok: bool, detail: str) -> None:
        checks["checks"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            checks["ok"] = False

    add("dataset_exists", dataset.exists(), str(dataset))
    add("baseline_spec_exists", spec_path.exists(), str(spec_path))
    try:
        assert_decision_safe(V4_META_FEATURES)
        add("v4_feature_contract", True, f"{len(V4_META_FEATURES)} causal features")
    except ValueError as exc:
        add("v4_feature_contract", False, str(exc))
    if dataset.exists():
        try:
            ds = pd.read_parquet(dataset)
            cols = set(ds.columns)
            add("dataset_feature_version", ds.attrs.get("feature_contract_version") == CONTRACT_VERSION,
                "requires current feature provenance; rebuild pre-audit datasets")
            missing = set(V4_META_FEATURES) - cols
            add("dataset_feature_schema", not missing,
                "all V4 features present" if not missing else f"missing {sorted(missing)}")
            required = {"entry_ts", "exit_ts", "executed", "net_return"}
            absent = required - cols
            add("dataset_execution_schema", not absent,
                "entry/exit/execution fields present" if not absent else f"missing {sorted(absent)}")
            # Option B (mark-to-market selection) readiness — informational, not
            # a hard failure: the standard simulator run does not need it.
            blockers = option_b_blockers(
                cols, mark_stream_exists=mark_stream_path(dataset).exists())
            checks["checks"].append({
                "name": "option_b_ready", "ok": not blockers,
                "detail": "ready for --marks" if not blockers else "; ".join(blockers)})
        except Exception as exc:
            add("dataset_readable", False, repr(exc))
    if spec_path.exists():
        try:
            spec = json.loads(spec_path.read_text())
            add("baseline_spec_parseable", "symbols" in spec,
                "symbols present" if "symbols" in spec else "missing symbols")
        except Exception as exc:
            add("baseline_spec_parseable", False, repr(exc))
    if require_gbt:
        add("lightgbm", importlib.util.find_spec("lightgbm") is not None,
            "installed" if importlib.util.find_spec("lightgbm") is not None else "install lightgbm")
    return checks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=config.META_DATASET_PARQUET)
    ap.add_argument("--baseline-spec", type=Path, default=config.BASELINE_SPEC_JSON)
    ap.add_argument("--require-gbt", action="store_true")
    args = ap.parse_args()
    result = check_environment(args.dataset, args.baseline_spec, require_gbt=args.require_gbt)
    print(json.dumps(result, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
