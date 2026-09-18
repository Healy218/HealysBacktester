"""Explicit, conservative admission for unresolved noncash actions.

Every original noncash record is retained and receives a treatment. Since the
available provider record does not establish a dated successor identity,
deliverable, or option outcome, the affected boundary is excluded from usable
feature and held-position history. No price factor, cash flow, or successor
holding is invented.
"""
from collections import defaultdict
from datetime import date

import pandas as pd

from nn_meta.v7.cash_actions import record_key
from nn_meta.v7.storage import identity

POLICY_ID = "v7-explicit-noncash-boundary-exclusion-20260918"


def _validate_record(row):
    if row.get("category") not in {"complex", "split"}:
        raise ValueError("Noncash admission accepts only noncash action records")
    if row.get("record_sha256") != identity(row["record"]):
        raise ValueError("Original noncash record changed")
    if not row.get("kind") or not row.get("scoped_symbols"):
        raise ValueError("Noncash record needs kind and scoped symbols")


def compile_noncash_treatments(records):
    """Return one explicit exclusion treatment for every pending record."""
    records = list(records)
    keys = [record_key(r) for r in records]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate noncash records")
    treatments = []
    for row in records:
        _validate_record(row)
        refs = [{k: row[k] for k in ("provider", "kind", "action_id", "record_sha256")}]
        treatment = {
            "schema": "v7-noncash-boundary-treatment-v1",
            "policy_id": POLICY_ID,
            "treatment": "explicit_boundary_exclusion",
            "kind": row["kind"],
            "effective_date": row.get("effective_date"),
            "scoped_symbols": sorted(set(row["scoped_symbols"])),
            "replaces": refs,
            "review_identity": identity({"policy_id": POLICY_ID, "replaces": refs}),
            "creates_price_factor": False,
            "creates_cash": False,
            "successor_identity_admitted": False,
            "stock_deliverable_admitted": False,
            "option_deliverable_admitted": False,
            "feature_history_admitted": False,
            "held_position_treatment": "reject_crossing_position",
            "rationale": "Provider noncash terms are retained, but exact successor identity and/or deliverable evidence is absent; exclude the boundary rather than infer a transition.",
        }
        treatments.append(treatment)
    return treatments


def build_exclusion_panel(history, records, treatments):
    """Mark exact dated boundaries and conservative undated identity spans."""
    originals = {record_key(r): r for r in records}
    if len(treatments) != len(records):
        raise ValueError("Treatment partition is incomplete")
    consumed = set()
    by_symbol = defaultdict(list)
    for treatment in treatments:
        refs = treatment.get("replaces", [])
        if len(refs) != 1:
            raise ValueError("One original record per noncash treatment required")
        key = record_key(refs[0])
        if key in consumed or key not in originals:
            raise ValueError("Treatment source partition differs")
        consumed.add(key)
        for symbol in treatment["scoped_symbols"]:
            by_symbol[symbol].append(treatment)
    if consumed != set(originals):
        raise ValueError("Every noncash record needs exactly one treatment")
    history = history.copy()
    if "history_admitted" not in history:
        history["history_admitted"] = True
    required = {"security_id", "source_date", "stock_ticker", "history_admitted"}
    if not required.issubset(history) or history.duplicated(["security_id", "source_date"]).any():
        raise ValueError("Unique history panel required")
    panel = history.copy()
    panel["noncash_treatment_ids"] = [[] for _ in range(len(panel))]
    panel["noncash_boundary_excluded"] = False
    if "held_position_admitted" in panel:
        panel["held_position_admitted"] = panel["held_position_admitted"].astype(bool)
    else:
        panel["held_position_admitted"] = False
    for i, row in panel.iterrows():
        symbol = row.get("stock_ticker")
        if pd.isna(symbol):
            continue
        hits = []
        for treatment in by_symbol.get(str(symbol), []):
            effective = treatment.get("effective_date")
            # An undated identity event cannot be bridged safely, so retain no
            # history for that ticker under this admission policy.
            if effective is None or str(row.source_date) >= str(effective):
                hits.append(treatment["review_identity"])
        if hits:
            panel.at[i, "noncash_treatment_ids"] = sorted(hits)
            panel.at[i, "noncash_boundary_excluded"] = True
            panel.at[i, "history_admitted"] = False
            panel.at[i, "held_position_admitted"] = False
            panel.at[i, "coverage_status"] = "explicit_noncash_boundary_exclusion"
    return panel


def require_boundary_safe(boundaries, *, security_id, source_dates):
    """Consumer guard for feature and held-position paths."""
    dates = {str(d)[:10] for d in source_dates}
    selected = boundaries[(boundaries.security_id == security_id) & boundaries.source_date.isin(dates)]
    if not selected.empty and selected.noncash_boundary_excluded.any():
        raise ValueError("Position or feature path crosses an excluded noncash boundary")
    return selected
