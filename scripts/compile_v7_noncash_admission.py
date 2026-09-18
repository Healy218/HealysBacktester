"""Compile every unresolved noncash record into an explicit exclusion panel."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import pandas as pd
    from nn_meta.v7.noncash_admission import compile_noncash_treatments, build_exclusion_panel, POLICY_ID
    from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
    p = argparse.ArgumentParser()
    p.add_argument("--unresolved", type=Path, required=True)
    p.add_argument("--history", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    records = json.loads(a.unresolved.read_text())
    verify(a.history)
    history = pd.read_parquet(a.history / "history.parquet")
    treatments = compile_noncash_treatments(records)
    panel = build_exclusion_panel(history, records, treatments)
    inputs = {str(a.unresolved): sha(a.unresolved), str(a.history / "complete.json"): sha(a.history / "complete.json"), str(ROOT / "nn_meta/v7/noncash_admission.py"): sha(ROOT / "nn_meta/v7/noncash_admission.py"), str(Path(__file__)): sha(Path(__file__))}
    report = {
        "schema": "v7-noncash-admission-v1",
        "policy_id": POLICY_ID,
        "original_records": len(records),
        "treated_records": len(treatments),
        "treatment_counts": pd.Series([x["kind"] for x in treatments]).value_counts().to_dict(),
        "history_rows": len(panel),
        "excluded_history_rows": int(panel.noncash_boundary_excluded.sum()),
        "held_position_admitted": False,
        "successor_identity_admitted": False,
        "feature_history_admitted": False,
        "research_ready": False,
        "inputs": inputs,
    }
    with transaction(a.output) as temp:
        (temp / "treatments.json").write_text(json.dumps(treatments, indent=2) + "\n")
        panel.to_parquet(temp / "coverage.parquet", index=False)
        (temp / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        receipt(temp, {"identity": identity(report), "research_ready": False})
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
