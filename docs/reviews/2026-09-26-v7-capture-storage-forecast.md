# V7 entry capture sample and storage forecast — September 26

All 1,440 predeclared quote/trade captures passed. The current per-window layout
does not have a supportable full-entry launch budget: its estimated 218.04 GB
exceeds both the 181.02 GB remaining acquisition quota and about 50.67 GB of
local capacity above the 100 GiB reserve. Training and bulk capture remain gated.
The original catalog, demand, union, kernel proof and first captures are intact.

## Population and sampling

`scripts/plan_v7_capture_sample.py` independently scanned all 591 sealed demand
databases and reconciled 76,910,536 requests, 2,223,844 contract-days, 21,015,267
paired union windows and 14,404,985,220 seconds per kind against the full audit.
The population remains all 591 securities, including explicit zero-demand cases.

The predeclared design has 60 strata: five years, four security request-count
quartiles, and three interval-duration buckets (at most 330 seconds, at most
600 seconds, longer). Request count is a demand-size proxy, not measured market
liquidity. Twelve paired windows per stratum are selected by the lowest seeded
SHA256 priorities, before any provider results are read. The resulting 720 pairs
cover 362 securities. Quote/trade pairing preserves covariance in byte estimates.
Parallel selection is identical to selecting priorities from the entire stream.

Plan: `nn_meta/validation/v7-entry-volume-sample-20260926`.
Its per-security scan checkpoints are preserved in the sibling `.checkpoints`
directory; they are derived sampling evidence, not replacements for demand.

## Actual capture and limits

`scripts/capture_v7_volume_sample.py` used four autosized outer workers and one
inner thread. The sealed plan allows at most 8 GiB sample acquisition, with
64 MiB additional metadata allowance, within the existing 640 GB project ceiling.
Before each group it checks full per-task reservations against sample, disk and
shared quota limits. Original capture/manifest validators verify every result.
Failures receive immutable attempt receipts and cannot be omitted from estimates.
Repeated runs reuse verified captures; the controller locks its exact output.

- 1,440 successful captures, zero failures, 237,417 records.
- 231,858 quote records and 5,559 trade records.
- 52 empty quote windows and 437 empty trade windows remain explicit.
- 620 captures before February 2024 contain 100,426 records. This is sampled
  older-history access evidence, not full historical coverage.
- 7,030,384 bytes including request/binding metadata; 186.55 seconds elapsed.
- Shared ledger after capture: 68,980,125,222 / 250,000,000,000 bytes;
  no outstanding reservations.

Raw: `nn_meta/data_v7/entry-volume-sample-20260926`.
Verified forecast: `nn_meta/validation/v7-entry-volume-forecast-20260926`.
Per-attempt receipts: sibling `.attempts` directory.
The separate Konsole progress viewer was opened on this exact run and now
shows completion. The obsolete completed-build alert timers remain disabled.

## Measured estimates and compression experiment

| Layout | Estimated capture bytes | Standard error | Mean plus three standard errors |
|---|---:|---:|---:|
| Existing immutable directories / gzip records | 218.04 GB | 15.91 GB | 265.77 GB |
| Experimental columns / zstd / compressed exact metadata | 164.08 GB | 12.40 GB | 201.28 GB |

These are stratified finite-population estimates under the hash-randomization
assumption. Three standard errors is a sensitivity measure, not a guaranteed
upper bound or a proved tail probability. Twelve pairs per stratum cannot rule
out heavy tails. Values exclude request mappings, dated references, additional
execution paths and some container/filesystem overhead. They are not full V7
resource forecasts or permission to exceed a cap.

A fresh whole-project `du -sb .` measurement returned **489,135,748,190 bytes**
(a non-atomic apparent-size read). Conservatively adding the full estimated
capture sizes gives 707.18 GB for the current layout or 653.22 GB for the
experimental layout, before other missing stages; both exceed the 640 GB
project ceiling. Already retained sample bytes are not subtracted in these
conservative additions. Capacity snapshot and parent bindings:
`nn_meta/validation/v7-entry-capacity-verdict-20260926`.

The experimental encoder preserves record order, duplicate prints, nanosecond
integers, floats, missing versus null fields and nested values. All 1,440 decoded
record streams match their original canonical bytes; original manifest and
receipt text also round-trips. Its index allowance is modeled at 128 bytes per
capture, not measured from a production container. No production archive reader,
migration, replacement or deletion was performed. Evidence:
`nn_meta/validation/v7-entry-encoding-benchmark-20260926`.

## Exact contiguous-range opportunity

The separate read-only `audit_v7_contiguous_captures.py` verified the full demand
again and merged only touching/overlapping intervals within a contract/day.
It reduced 42,030,534 fixed-cell captures to **10,941,828 contiguous ranges**:
5,470,914 per kind. All 2,223,844 contract-days and exact requested nanoseconds
reconcile; **zero seconds were added**. This is about 74% fewer logical ranges.
There are 1,975,031 paired ranges at most 15 minutes, 2,273,742 between 15 and
60 minutes, and 1,222,141 longer than one hour.

Evidence: `nn_meta/validation/v7-contiguous-entry-union-20260926`.
This count is not a measured long-range download forecast. Dense intervals may
need pagination splitting, and larger windows require bounded memory and a
tested receipt/archive path. The original fixed-cell audit remains unchanged.

## Remaining launch requirements

The user was asked which additional storage location is available. Read-only
inventory sees an unmounted 1.8 TiB exFAT partition labeled MRHA at `/dev/sda2`;
its contents/free space and suitability have not been inspected. It has not
been mounted, formatted, written to or admitted as project storage.

Next: resolve storage placement, measure exact contiguous-range capture and
retention costs, implement/validate any changed archive consumer, and produce
an updated full-project/acquisition forecast. A larger disk alone does not
change the 250 GB acquisition or 640 GB project limits. Keep all originals;
do not trim the research scope or erase historical artifacts to make it fit.
Dated standard references/class hours, fills/marks/exits/rolls/delivery, execution,
assembly and readiness still precede training. V7-3 remains open.

Validation: final full suite passed **2,424 tests plus 18 subtests**, with 20
warnings in 128.23 seconds. All nine focused sample/encoding/range tests pass.
