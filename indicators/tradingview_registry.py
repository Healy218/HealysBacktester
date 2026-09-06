"""Verified inventory of the thirteen selected TradingView publications.

This catalog is separate from active proposal families. Source acquisition and
local formula tests do not establish TradingView numerical parity. The report
binds exact Pine bytes, adaptation records and runtime code for fixture capture
and review; it never enables a family or changes a live model.

Run ``./venv/bin/python -m indicators.tradingview_registry`` from any directory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "docs/specs/tradingview-boost-snapshot-2026-09-05.json"
SOURCES = "indicators/tradingview_sources"


class SourceIntegrityError(ValueError):
    pass


def _file(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise SourceIntegrityError(f"missing or unsafe source dependency: {name}")
    return path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_catalog(root: Path = ROOT) -> dict:
    root = Path(root)
    snapshot = json.loads(_file(root, SNAPSHOT).read_text())
    selected = []
    for dataset in snapshot["datasets"]:
        rows = dataset["ranked_rows"]
        if len({row["id"] for row in rows}) != dataset["reported_total"]:
            raise SourceIntegrityError("ranking inventory does not match reported total")
        if rows != sorted(rows, key=lambda row: -row["boosts"]):
            raise SourceIntegrityError("ranking is not descending by boosts")
        for rank, row in enumerate(rows[:dataset["selected_count"]], 1):
            selected.append({**row, "listing": dataset["name"], "rank": rank})
    if len(selected) != 13 or {row["id"] for row in selected} != set(snapshot["selected_unique_ids"]):
        raise SourceIntegrityError("selection must match thirteen unique snapshot publications")

    source_records = {}
    structure = json.loads(_file(root, SOURCES + "/structure_sources.json").read_text())
    for record in structure["sources"]:
        source_records[record["script_id"]] = {
            "path": record["path"], "sha256": record["sha256_source"],
            "publication_version": str(record["publication_version"]),
            "pine_id": record["pine_id"], "returned_version": record["source_metadata"]["version"],
            "imports": record["imports"], "source_record": SOURCES + "/structure_sources.json",
        }
    trend_path = SOURCES + "/trend_manifest.json"
    for record in json.loads(_file(root, trend_path).read_text())["scripts"]:
        source_records[record["public_id"]] = {
            "path": SOURCES + "/" + record["source_file"], "sha256": record["sha256"],
            "publication_version": str(record["publication_version"]),
            "pine_id": record["pine_id"], "returned_version": record["returned_version"],
            "imports": record["imports"], "source_record": trend_path,
        }
    adaptations = {}
    for path in sorted((root / SOURCES).glob("*_manifest.json")):
        manifest = json.loads(path.read_text())
        for record in manifest.get("scripts", []):
            if not record.get("implementation_module"):
                continue
            script_id = record["public_id"]
            if script_id in adaptations:
                raise SourceIntegrityError(f"duplicate adaptation record: {script_id}")
            adaptations[script_id] = (path, record)

    output = []
    for row in selected:
        script_id = row["url"].split("/script/", 1)[1].split("/", 1)[0].split("-", 1)[0]
        if script_id not in source_records:
            raise SourceIntegrityError(f"missing selected source: {script_id}")
        source = source_records[script_id]
        if str(row["publication_version"]) != source["publication_version"]:
            raise SourceIntegrityError(f"source revision differs from ranking snapshot: {script_id}")
        if source["pine_id"] != row["pine_id"] or source["returned_version"] != source["publication_version"] + ".0":
            raise SourceIntegrityError(f"source acquisition identity differs from snapshot: {script_id}")
        if _digest(_file(root, source["path"])) != source["sha256"]:
            raise SourceIntegrityError(f"Pine source hash mismatch: {script_id}")
        entry = {"script_id": script_id, "title": row["title"], "author": row["author"],
                 "url": row["url"], "listing": row["listing"], "rank": row["rank"],
                 "boosts_at_capture": row["boosts"], "source": source,
                 "status": "source_pinned", "active_pool_admission": False}
        if script_id in adaptations:
            manifest_path, record = adaptations[script_id]
            if record["sha256"] != source["sha256"]:
                raise SourceIntegrityError(f"adaptation refers to different source: {script_id}")
            if record["pine_id"] != source["pine_id"] or str(record["publication_version"]) != source["publication_version"]:
                raise SourceIntegrityError(f"adaptation publication identity differs: {script_id}")
            dependencies = {record["implementation_module"],
                            *record.get("required_runtime_helpers", [])}
            # Shared math/validation are semantic dependencies even for the
            # earliest adaptation manifests that predate this catalog.
            dependencies.update(("v3/pine_compat.py", "v3/_tv_trend_support.py"))
            wrapper = record.get("signal_wrapper")
            if wrapper:
                dependencies.add(wrapper.rsplit(".", 1)[0].replace(".", "/") + ".py")
                dependencies.add("signals/tv_signals.py")
                if wrapper.startswith("signals.tv_trend_signals."):
                    dependencies.add("v3/tv_trend_indicators.py")
            hashes = {name: _digest(_file(root, name)) for name in sorted(dependencies)}
            identity = {"source_sha256": source["sha256"], "runtime_sha256": hashes,
                        "adaptation_sha256": _digest(manifest_path)}
            entry.update(status="implemented_pending_external_parity",
                         adaptation_manifest=str(manifest_path.relative_to(root)),
                         implementation_module=record["implementation_module"],
                         input_contract=record.get("input_contract"),
                         port_scope=record.get("port_scope"),
                         excluded_scope=record.get("excluded_scope"),
                         unverified_edges=record.get("unverified_edges"), identity=identity,
                         fixture_identity_sha256=hashlib.sha256(
                             json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
                         ).hexdigest())
        output.append(entry)
    return {"schema_version": 1, "ranking_snapshot": SNAPSHOT,
            "ranking_snapshot_sha256": _digest(_file(root, SNAPSHOT)),
            "selection_count": len(output), "scripts": output,
            "admission_note": "External TradingView fixtures and scoped data/signal contracts remain required. This inventory does not admit families."}


def main() -> None:
    print(json.dumps(build_catalog(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
