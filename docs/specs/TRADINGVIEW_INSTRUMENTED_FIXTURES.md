# Instrumented plots and replay-terminal fixtures

The fixture importer accepts reviewed observation plots without identifying the
edited Pine file as the unmodified publication. It compares declared outputs and
never changes source registry status or model admission. Actual TradingView
compilation and chart captures remain required; test-suite CSVs are synthetic.

The initial capture pack is `docs/capture_templates/tradingview/`: three private
trend copies, their unreviewed receipts and a separate context helper. Every copy
preserves the exact licensed original bytes and appends observations. Nothing in
the pack has been compiled or executed on TradingView. Preserve the upstream
copyright/license and keep the copies private; capture provenance is separate from
license/admission review.

### Split captures for Pine's plot limit

The original three drafts append 17, 27 and 22 observation plots. Pine limits
each script to 64 plot counts, including series colors, alerts and some fills;
counting `plot()` statements alone underestimates usage. In particular the
Fibonacci draft adds 27 to an already plot-heavy original. Actual compilation
has not yet established the final counts. See
[TradingView's limits](https://www.tradingview.com/pine-script-docs/writing/limitations/).

Generate smaller append-only drafts without changing the publication:

```bash
./venv/bin/python -m scripts.prepare_tradingview_harnesses \
  --output /absolute/path/to/new-split-harnesses --run
```

The default adds at most eight plots per source copy, repeating bar index,
close time and confirmed state in each shard. All other declared observations
are retained across the shards. The three existing drafts produce twelve
copies (Gaussian three, Fibonacci five, Uptrick four). Input draft receipts
must match their regenerated unreviewed receipts exactly; completed reviews
are preserved separately. Each new receipt starts unreviewed and uncompiled.
This budget is preparation, not a claim that TradingView compiled the result.

Capture each source's shards with identical settings and complete history.
Each actual export becomes its own parity-pack fixture, with its own completed
receipt and only the Python fields mapped by that receipt. Retain all source
and context files. Do not splice rows from different history origins. Without
`--run`, the command only previews the shard/file plan.

## Source receipt

`scripts.tradingview_fixture.instrumentation_append(plots)` renders a fixed suffix.
Each plot specifies exactly `title`, `expression`, `kind` and `python_column`.
Titles are unique `TVF:` identifiers; `python_column: null` identifies a context
observation that cannot be mapped as a source algorithm output. The supported
grammar is deliberately narrow: existing numeric variables, existing zero/one
event flags (including two flags joined by `and`), selected bar/session flags,
ATR14, default `ta.vwap(hlc3)` and `timeframe.change("2D")`. Assignments, arbitrary
calls, new state and changed source statements fail. Exposing an array/local-block
value needs a separately reviewed future instrumentation contract.

`prepare_instrumentation_receipt(script_id, pine_path, plots)` verifies exact
original-prefix bytes and produces original/edited/suffix hashes plus an exact
unified diff and its hash. Review and compilation fields begin false. A reviewer
must verify the observed variables and update order, record their identity and
offset-bearing review time, and bind `reviewed_diff_sha256`. Set
`compiled_on_tradingview` only after actual successful compilation; these fields
are attestations, not authenticated signatures. The tool recomputes the suffix,
source and diff instead of trusting user-supplied hashes. Header/version/license
edits and edits to existing code fail even when their replacement hashes are supplied.

For instrumented chart exports use metadata schema 2, keep the original `source`
and registry `fixture_identity_sha256`, set `source_verified_against_chart` to
**false**, and add:

```json
{
  "source_capture": {
    "kind": "reviewed_append_only_plots",
    "receipt_sha256": "canonical hash_json of the completed reviewed receipt",
    "instrumented_source_verified_against_chart": true
  }
}
```

The last flag refers specifically to the edited source actually running on the
chart. Each comparison mapping also includes `instrumented_plot_title`, for
example `TVF:trend_line`, while `tv_column` names the actual CSV header. The
reviewed receipt binds that plot's Python column and numeric/event kind. Mapping
an event as numeric to introduce tolerance fails. The remaining capture, parameter,
OHLCV, precision and history requirements are unchanged from
`TRADINGVIEW_FIXTURE_RUNBOOK.md`.

```bash
./venv/bin/python -m scripts.tradingview_fixture validate \
  --csv /tmp/capture.csv --metadata /tmp/capture.json \
  --instrumentation-manifest /tmp/reviewed-receipt.json \
  --instrumented-source /tmp/capture-source.pine \
  --report /tmp/comparison-report.json
```

The Python API keeps all original arguments and adds
`instrumentation_manifest=<receipt dict>, instrumented_source=<path>` to
`compare_fixture`. Report identity includes both original and executed source,
the receipt/diff, full input hash, comparison metadata and validator hash. CLI
evidence files cannot alias the report, and their hashes are rechecked before
writing. To assess an existing report, rerun comparison against its retained raw
files and declared metadata; editing a report is not a new validation.

Schema 1 remains the unmodified publication workflow. Schema 2 may also declare
`source_capture: {"kind": "unmodified_publication"}` with the original true source
attestation and no instrumentation files. This supports terminal snapshots of
native plots without requiring an edited source.

## Terminal scope and execution history

The default scope is `{"kind":"full_series"}`. For a value calculated only at
the chart's last bar, schema 2 can declare this structure (replace every time with
the actual capture):

```json
{
  "comparison_scope": {
    "kind": "terminal_snapshot",
    "terminal_bar_open": "2025-01-02T15:00:00+00:00",
    "execution": {
      "mode": "continuous_replay",
      "history_origin": "2024-12-02T14:30:00+00:00",
      "sequence_verified": true,
      "steps": [
        {"action":"load", "terminal_bar_open":"2025-01-02T14:30:00+00:00"},
        {"action":"forward", "terminal_bar_open":"2025-01-02T14:45:00+00:00"},
        {"action":"forward", "terminal_bar_open":"2025-01-02T15:00:00+00:00"}
      ]
    }
  }
}
```

The CSV and local calculation still contain **every calculation-history bar**.
Only the final input row is compared; reports distinguish full `rows` from
`compared_rows` and name the exact compared terminal. Warmup is never truncated.
Continuous replay must record every available bar from the initial replay load
to the terminal in order. `fresh_load` instead requires exactly one load step at
the terminal. The tool validates sequence structure and identity; it does not
authenticate that UI actions occurred or simulate source `var` state automatically.
A local producer for a stateful profile must implement the same declared
execution semantics and preserve its command/code for review.

This distinction matters for the POC and Footprint sources' `barstate.islast`
blocks. Footprint can retain stale POC between last-bar executions; fresh loading
and continuous replay are different evidence cases. Source plots, full OHLCV
prefixes, replay endpoints and available-at times must be captured directly. The
TradingView UI's replay download behavior must first be confirmed; no claim is
made that ordinary CSV download contains historical last-bar profile values.

For other adapters, precomputed local CSV metadata now binds schema-2 source
capture and comparison scope hashes in addition to original OHLCV/capture/parameter
identity. A local CSV attested for one execution sequence cannot be reused under
another sequence without an explicit new producer binding. This does not prove
that the declared producer generated its values. One terminal match does not
establish full-series or all-branch parity.

## Context helper

The standalone helper exposes raw OHLCV, ATR14, `timeframe.change("2D")`, the
actual default VWAP, session flags, bar index, close time and confirmed/last-bar
flags. Its hash is separate from every publication identity. Exact `2D` flags
are useful to the HTF port. Default VWAP is an observed series; no equivalence to
an assumed daily/session reset flag is asserted. Use the feature bridge's
`vwap_observations` route when available. Helper outputs must be retained and
bound as external context, not relabeled as upstream strategy signals.

The all-thirteen capture matrix in the pack lists native plots versus required
observations and replay evidence. The first three harnesses cover trend outputs;
there is no all-thirteen Pine compilation or parity claim.

## Explicitly unavailable numerical outputs

A default numerical mapping still requires at least one finite pair. To verify an
inactive session column or a warmup terminal state, a mapping may explicitly add
`"expectation":"unavailable"` with `kind: numeric`, `nan_policy: match`, and both
tolerances zero. Every selected value must be missing on **both** platforms. Any
finite value or one-sided missing value rejects intake; no rows are dropped.
Event columns cannot use this mode: false remains an exact observed boolean.

The column result is `status: matched_unavailable`, `evidence_kind: missingness_only`,
zero finite pairs and no numerical error value. A report containing only these
columns is `matched_unavailable`; a successful mixture is `matched_with_unavailable`.
The normal `matched` status remains for finite numerical/event evidence. All three
successful statuses return CLI exit 0; downstream consumers must preserve the
distinction and the explicit `unavailable_columns` list. Missingness agreement
does not establish numerical parity when that feature becomes active.

Terminal scope applies the same check only to the explicitly selected final bar,
while retaining every initialization bar and the execution sequence in report
identity. The expectation is bound by the complete metadata hash and must be
retained when rerunning a comparison. Changing a report label cannot create this
evidence; comparison must be rerun from the raw files and declared mapping.
