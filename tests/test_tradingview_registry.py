"""Publication identity must survive acquisition and adaptation unchanged."""
from pathlib import Path
import shutil
import json

import pytest

from indicators.tradingview_registry import ROOT, build_catalog, SourceIntegrityError


@pytest.fixture
def catalog_root(tmp_path):
    for directory in ("indicators/tradingview_sources", "docs/specs", "v3", "signals"):
        destination = tmp_path / directory
        destination.mkdir(parents=True)
        for path in (ROOT / directory).glob("*"):
            if path.is_file() and path.suffix in (".json", ".py", ".pine"):
                shutil.copy2(path, destination / path.name)
    return tmp_path


def test_all_thirteen_exact_publications_are_cataloged():
    catalog = build_catalog()
    assert catalog["selection_count"] == 13
    assert len({row["script_id"] for row in catalog["scripts"]}) == 13
    assert all(row["active_pool_admission"] is False for row in catalog["scripts"])
    assert catalog["scripts"][0]["script_id"] == "hkKioUnL"
    assert [r["script_id"] for r in catalog["scripts"][-3:]] == ["DkE7UniD", "nW5oGfdO", "Ej53t8Wv"]


def test_changed_pine_bytes_refuse_identity(catalog_root):
    path = catalog_root / "indicators/tradingview_sources/AqRNdhlR_v1.pine"
    path.write_bytes(path.read_bytes() + b"\n// changed\n")
    with pytest.raises(SourceIntegrityError, match="Pine source hash mismatch"):
        build_catalog(catalog_root)


def test_shared_runtime_changes_invalidate_fixture_identity(catalog_root):
    def identity():
        return next(row["fixture_identity_sha256"] for row in build_catalog(catalog_root)["scripts"]
                    if row["script_id"] == "AqRNdhlR")
    before = identity()
    path = catalog_root / "v3/pine_compat.py"
    path.write_bytes(path.read_bytes() + b"\n# changed helper\n")
    assert identity() != before


def test_missing_runtime_dependency_refuses_fixture_identity(catalog_root):
    (catalog_root / "v3/pine_compat.py").unlink()
    with pytest.raises(SourceIntegrityError, match="missing or unsafe"):
        build_catalog(catalog_root)


@pytest.mark.parametrize("field", ["pine_id", "returned_version"])
def test_conflicting_acquisition_identity_refused(catalog_root, field):
    path = catalog_root / "indicators/tradingview_sources/structure_sources.json"
    data = json.loads(path.read_text())
    if field == "pine_id":
        data["sources"][0]["pine_id"] = "PUB;WRONG_PUBLICATION"
    else:
        data["sources"][0]["source_metadata"]["version"] = "999.0"
    path.write_text(json.dumps(data))
    with pytest.raises(SourceIntegrityError, match="acquisition identity"):
        build_catalog(catalog_root)
