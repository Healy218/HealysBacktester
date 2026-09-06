"""Split draft observation plots into bounded append-only capture harnesses.

The added-plot budget is not a Pine compiler result. Every output retains the
entire original publication and still requires actual review and compilation.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

from scripts import tradingview_fixture as fixture
from scripts.prepare_v6_parity_pack import _fresh_directory, _write
from nn_meta.v6_expansion import sha256

DEFAULT_DRAFTS = fixture.ROOT / "docs/capture_templates/tradingview"
HISTORY_EXPRESSIONS = {"bar_index", "time_close", "barstate.isconfirmed ? 1 : 0"}


def split_plots(plots, max_added_plots=8):
    """Repeat history observations in every shard and retain each other plot."""
    fixture.instrumentation_append(plots)  # validate complete list before splitting
    if isinstance(max_added_plots, bool) or not isinstance(max_added_plots, int):
        raise ValueError("added-plot budget must be an integer")
    common = [p for p in plots if p["python_column"] is None and p["expression"] in HISTORY_EXPRESSIONS]
    if {p["expression"] for p in common} != HISTORY_EXPRESSIONS or len(common) != 3:
        raise ValueError("draft must expose exactly one bar index, close time and confirmed observation")
    if not 4 <= max_added_plots <= 8:
        raise ValueError("added-plot budget must be between 4 and 8; upstream plots also consume the 64-count limit")
    remaining = [p for p in plots if p not in common]
    if not remaining:
        raise ValueError("draft contains no non-history observations")
    size = max_added_plots - len(common)
    return [deepcopy(remaining[offset:offset + size] + common)
            for offset in range(0, len(remaining), size)]


def prepare(args):
    output = _fresh_directory(args.output)
    # Read and verify the existing drafts before writing any generated files.
    plans, inputs = [], {}
    for receipt_path in sorted(args.drafts.glob("*_receipt_DRAFT.json")):
        receipt_hash = sha256(receipt_path)
        receipt = fixture.load_metadata(receipt_path)
        script = receipt["script_id"]
        source_path = args.drafts / f"{script}_capture_DRAFT.pine"
        source_hash = sha256(source_path)
        regenerated = fixture.prepare_instrumentation_receipt(script, source_path, receipt["plots"])
        if receipt != regenerated:
            raise ValueError("input must be an unchanged unreviewed draft receipt; preserve completed reviews separately")
        original_path = fixture.ROOT / fixture._entry(script)["source"]["path"]
        original_hash = sha256(original_path)
        original = original_path.read_bytes()
        inputs.update({str(p.absolute()): digest for p, digest in (
            (receipt_path, receipt_hash), (source_path, source_hash), (original_path, original_hash))})
        shards = split_plots(receipt["plots"], args.max_added_plots)
        plans.append((script, original, shards))
    if not plans or len({p[0] for p in plans}) != len(plans):
        raise ValueError("supply distinct source drafts; no draft receipts found or duplicate source")
    manifest = {"schema": "tradingview-split-harnesses-v1", "status": "unreviewed_uncompiled",
        "max_added_plots": args.max_added_plots, "source_count": len(plans),
        "upstream_plot_count_verified": False, "compiled_on_tradingview": False,
        "external_parity": False, "model_admission": False, "input_files": inputs,
        "sources": [], "files_sha256": {},
        "capture_instructions": [
            "Compile and review every used shard in TradingView; the plot budget is not a compiler attestation.",
            "For each source, capture all shards on identical chart settings and complete OHLCV histories.",
            "Each shard repeats bar index, close time and confirmed state for history checks.",
            "Add one parity-pack fixture per actual export, mapping only the fields plotted in its reviewed receipt.",
            "Do not combine CSV rows from differing histories or relabel drafts as actual captures."]}
    if args.run:
        output.mkdir(parents=True, exist_ok=False)
    for script, original, shards in plans:
        record = {"script_id": script, "shards": []}
        for index, plots in enumerate(shards, 1):
            stem = f"{script}_part_{index:02d}"
            source_path = output / f"{stem}_capture_DRAFT.pine"
            receipt_path = output / f"{stem}_receipt_DRAFT.json"
            record["shards"].append({"source": source_path.name, "receipt": receipt_path.name,
                "added_plot_count": len(plots),
                "python_columns": [p["python_column"] for p in plots if p["python_column"] is not None]})
            if args.run:
                with source_path.open("xb") as stream:
                    stream.write(original + fixture.instrumentation_append(plots))
                _write(receipt_path, fixture.prepare_instrumentation_receipt(script, source_path, plots))
                for path in (source_path, receipt_path):
                    manifest["files_sha256"][path.name] = sha256(path)
        manifest["sources"].append(record)
    for path, digest in inputs.items():
        if sha256(path) != digest:
            raise ValueError("draft/source inputs changed while preparing harnesses")
    if args.run:
        _write(output / "manifest.json", manifest)
    return {"written": args.run, "output": str(output), **manifest}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--drafts", type=Path, default=DEFAULT_DRAFTS)
    ap.add_argument("--max-added-plots", type=int, default=8)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args(argv)
    try:
        result = prepare(args)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"TRADINGVIEW-HARNESSES-FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
