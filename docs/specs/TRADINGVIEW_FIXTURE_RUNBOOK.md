# TradingView fixture capture and comparison

This workflow consumes an actual user-exported chart CSV. It creates a scoped
comparison report; it does not admit a strategy, change registry status, or
authenticate where a supplied file came from. Test-suite CSVs are synthetic
software tests and are never external parity evidence.

## Capture

Use standard candles with completed bars. Record the exact symbol **and exchange**,
fixed intraday timeframe, chart timezone, session selection, price-adjustment
setting, instrument minimum tick, indicator input settings, and pinned source
revision. Keep the complete calculation history from the same first bar on both
platforms. A cropped export cannot initialize an equivalent recursive calculation.
Record the UTC-offset capture time after the last exported bar has closed.

Export chart data including OHLCV and the desired indicator plots. Keep the original
CSV bytes. Plot names differ between scripts; inspect actual headers and map them
explicitly. A plot unavailable in the export is outside this fixture's coverage.
Do not invent an alert column from a description or treat a chart marker's price
as a boolean. An instrumented Pine capture requires separately reviewed source
provenance; the pinned-publication identity must not silently stand for edited Pine.

Generate an **incomplete** sidecar using the actual CSV headers, for example:

```bash
./venv/bin/python -m scripts.tradingview_fixture template \
  --csv /tmp/tv-capture.csv --script-id AqRNdhlR \
  --timezone America/New_York --time-column time --timestamp-encoding iso8601 \
  --ohlcv-columns open high low close Volume > /tmp/tv-capture.json
```

Use `unix_s` or `unix_ms` instead of `iso8601` for integer epoch exports. Naive ISO
timestamps are interpreted in the declared chart timezone; ambiguous/nonexistent
DST times fail. Offset-bearing timestamps retain their instant and normalize to
UTC. Only bar-open timestamps and fixed `s`, `m`, or `h` timeframes are currently
supported; daily/calendar bars and synthetic chart types need a separate contract.

Fill every null capture field, use a timeframe such as `15m`, and choose
`price_adjustment` from `raw`, `splits`, or `splits_dividends`. Confirm the exact
source revision and every parameter against the chart before setting
`source_verified_against_chart` and `inputs_verified_against_chart` to true.
Set both history/closed-bar attestations only when verified. Template parameters
are local defaults for convenience, **not** evidence of the captured settings.
The template binds the Pine revision, current runtime/adaptation identity, CSV
bytes, and canonical timestamp/OHLCV hash. Changed identities require review and
new binding; never change a hash just to conceal a mismatch.

Declare one mapping per desired output in `columns`. Example mapping shapes
(replace names with actual exported plots and actual Python output names):

```json
[
  {"tv_column":"Actual numerical plot", "python_column":"trend_line",
   "kind":"numeric", "atol":0.000001, "rtol":0,
   "nan_policy":"match"},
  {"tv_column":"Actual 0/1 alert plot", "python_column":"bull_signal",
   "kind":"event", "atol":0, "rtol":0,
   "nan_policy":"forbid", "event_encoding":"zero_one"}
]
```

Choose and justify numeric tolerances using the export precision and output units.
The test is `abs(Python - TV) <= atol + rtol * abs(TV)`. `match` requires identical
NaN locations, including warmup; `forbid` rejects any missing values. Rows are never
dropped or shifted. All-missing numerical comparisons fail. Event comparison is
exact at the same timestamp with no numerical tolerance. A documented plot that
exports one for true and missing for false may explicitly use `one_or_missing`
with `nan_policy: missing_is_false`; arbitrary prices, nonbinary values, or mixed
encodings fail. Reports include true-event counts; all-false agreement does not
exercise an alert transition.

## Compare

Direct calculation is available for Gaussian `AqRNdhlR`, Fibonacci `U7CZ8jtj`, and
Uptrick `f4N0F439`. Their parameter objects must contain all supported inputs.
Uptrick's `minimum_tick` must also equal the captured instrument tick.

```bash
./venv/bin/python -m scripts.tradingview_fixture validate \
  --csv /tmp/tv-capture.csv --metadata /tmp/tv-capture.json \
  --report /tmp/tv-capture-report.json
```

Exit status is 0 for declared columns matched, 1 for actual mismatches, and 2 for
invalid intake. Reports bind the validator hash, source/runtime identity, capture,
parameters and input. They show per-column counts, numerical errors and first
mismatch timestamps. No runtime registration or active-pool state is written.
Parsed CSVs use one byte snapshot; input/local CSV and runtime/validator identities
are checked again after comparison and before report writing. Report destinations
cannot alias any intake CSV or metadata file, including symlinks and hard links.
Reports record actual Python, NumPy and pandas versions. Built-in boolean outputs
must use exact event comparison; a numerical tolerance cannot waive alert differences.
An invalid intake does not replace a prior report; always check the command's
exit status and keep each capture/report in a separate evidence directory.

## Optional precomputed Python outputs

For other scoped adapters, supply `--local-csv` and `--local-metadata`. The CSV must
contain canonical columns `time,Open,High,Low,Close,Volume` plus the declared Python
outputs. Use offset-bearing ISO timestamps, exact original OHLCV, and zero/one
events. Do not resample, shift, truncate warmup, or substitute provider bars.
Writing float64 values with `float_format="%.17g"` preserves round-trip precision.

The producer creates a metadata sidecar using the completed capture metadata:

```python
import json
from scripts.tradingview_fixture import load_metadata, local_csv_metadata
capture = load_metadata("/tmp/tv-capture.json")
binding = local_csv_metadata(capture, "/tmp/python-output.csv",
                             producer="Describe the exact local calculation command")
with open("/tmp/python-output.json", "w") as stream:
    json.dump(binding, stream, indent=2)
```

This records local CSV bytes, registry identity, input OHLCV hash, capture hash,
parameter hash and producer declaration. Validation also independently recomputes
the local CSV's OHLCV hash; metadata alone cannot excuse different bars. This mode
does not prove that the declared producer actually generated the values. Preserve
the producer command, code revision and raw exports for review.

A matched report covers only its mapped outputs, input history and settings.
Additional source edges, historical/live causality, data dependencies, license
scope and pool admission still require their own review.
