"""Source-preservation tests, not Pine compilation or external parity evidence."""
from collections import Counter
import json
from types import SimpleNamespace

import pytest

from scripts import prepare_tradingview_harnesses as harness


def drafts():
    return [harness.fixture.load_metadata(p)
            for p in sorted(harness.DEFAULT_DRAFTS.glob("*_receipt_DRAFT.json"))]


@pytest.mark.parametrize("draft", drafts(), ids=lambda d: d["script_id"])
def test_split_preserves_every_observation_and_repeats_history(draft):
    shards = harness.split_plots(draft["plots"])
    assert len(shards) > 1
    expected = Counter(p["title"] for p in draft["plots"] if p["expression"] not in harness.HISTORY_EXPRESSIONS)
    observed = Counter()
    for plots in shards:
        assert len(plots) <= 8
        assert {p["expression"] for p in plots if p["python_column"] is None} >= harness.HISTORY_EXPRESSIONS
        observed.update(p["title"] for p in plots if p["expression"] not in harness.HISTORY_EXPRESSIONS)
    assert observed == expected
    shards[0][0]["expression"] = "changed"
    assert draft["plots"][0]["expression"] != "changed"


@pytest.mark.parametrize("budget", [3, 9, 64, True, 4.5])
def test_invalid_budget_rejected(budget):
    with pytest.raises(ValueError, match="budget"):
        harness.split_plots(drafts()[0]["plots"], budget)


def test_missing_history_observation_rejected():
    plots = [p for p in drafts()[0]["plots"] if p["expression"] != "bar_index"]
    with pytest.raises(ValueError, match="bar index"):
        harness.split_plots(plots)


def test_prepare_is_preview_first_and_written_sources_retain_exact_prefix(tmp_path):
    args = SimpleNamespace(drafts=harness.DEFAULT_DRAFTS, max_added_plots=8, output=tmp_path / "new", run=False)
    preview = harness.prepare(args)
    assert not args.output.exists() and not preview["written"]
    args.run = True
    result = harness.prepare(args)
    assert result["source_count"] == 3
    assert not result["compiled_on_tradingview"] and not result["external_parity"]
    for source in result["sources"]:
        original = (harness.fixture.ROOT / harness.fixture._entry(source["script_id"])["source"]["path"]).read_bytes()
        for shard in source["shards"]:
            source_path = args.output / shard["source"]
            receipt = json.loads((args.output / shard["receipt"]).read_text())
            assert source_path.read_bytes() == original + harness.fixture.instrumentation_append(receipt["plots"])
            assert receipt == harness.fixture.prepare_instrumentation_receipt(source["script_id"], source_path, receipt["plots"])
            assert not receipt["review"]["reviewed"] and not receipt["compiled_on_tradingview"]
    assert (args.output / "manifest.json").is_file()
    with pytest.raises(ValueError, match="fresh"):
        harness.prepare(args)


def test_changed_draft_receipt_fails_without_output(tmp_path):
    directory = tmp_path / "drafts"
    directory.mkdir()
    draft = drafts()[0]
    script = draft["script_id"]
    draft["review"]["reviewed"] = True
    (directory / f"{script}_receipt_DRAFT.json").write_text(json.dumps(draft))
    source = f"{script}_capture_DRAFT.pine"
    (directory / source).write_bytes((harness.DEFAULT_DRAFTS / source).read_bytes())
    output = tmp_path / "out"
    assert harness.main(["--drafts", str(directory), "--output", str(output), "--run"]) == 1
    assert not output.exists()
