# ETFE 0DTE, normalization and bounded expansion — October 4, 2026

The user explicitly permits same-day options when signals qualify and directs
normalization and expanded acquisition. This successor overrides the one-day
minimum in [v3](ETFE_DTE_20261004.md). Actual new-entry/roll range is **0–5 calendar
DTE**, default targets **0/1/5**, with conditional weekly targets **2/4**. Target 7
stays removed. Twenty families, 1/5/15-minute signals, Alpaca-only data and the
fixed October 2, 2026 inclusive end remain. The machine scope is
[v4](ETFE_SCOPE_0DTE_20261004.json); predecessor artifacts stay unchanged.

0DTE requires a qualifying causal signal and all normal entry guards. Do not
enter at/after the existing expiry exit cutoff (dated contract close minus
15 minutes). Unknown dated expiry close withholds that entry rather than using
stock hours as option hours. Exit/settlement and stop rules remain. A DTE guard
is a component, not a complete signal/execution engine. New dte_frac remains
DTE/5, including zero. A same-day IV proxy must use positive seconds to the
verified expiry close divided by 365×86400; do not substitute zero or one day
for remaining time. Missing/expired expiry clocks produce missing IV.

## Typed normalization

Read only complete, checksummed fresh Alpaca page chains. Bind each normalized
run to capture plans, a newly fetched Alpaca calendar, v4 scope and exact code.
Output per-source-job Parquet with explicit dtypes, UTC int64 nanoseconds,
native timestamp text, raw JSON, symbol and original occurrence lineage (plan,
job, page, row and body hash). Parquet is a typed representation, not a new
point-in-time or execution admission. Preserve all no-ID trade occurrences.

Finite price, integer volume/count/size, OHLC, minute alignment, condition,
identity and duplicate checks produce row flags and partition counts. Invalid
values remain in raw JSON and receive null typed values where conversion fails.
Do not forward-fill, zero-fill or fabricate minute bars. Equal bar keys are
reported as identical/conflicting while retaining all raw occurrences. Identical
trade content is counted, not deduplicated or assumed to be duplicate delivery.
Raw contract listings remain discovery-only; no economic multiplier repair.

Join observations to freshly fetched Alpaca **stock** calendar sessions in New
York. Record inside/outside stock regular hours explicitly; this classification
does not assert option-class hours. Report expected versus observed stock regular
minutes, including holidays/early closes, with missing intervals classified as
unresolved gaps. A missing VOO minute alone cannot prove no trading. Report
option observations without inventing a complete option-session minute grid.

Bound writes to 5,000-row batches and one source partition at a time. Publish
checksummed Parquet before immutable partition receipts. Interrupted orphan
files are not committed; resume reuses verified completed partitions. Seal only
when every planned partition reconciles raw and typed row counts. Fail on input,
code, calendar or committed-output hash drift. Checks are independent from
the later feature/label admission and input freeze.

## Expansion authorized in this revision

1. Fresh Alpaca stock calendar from January 1, 2024 through October 2, 2026.
2. All three ETFs' remaining stock months, February 2024–September 2026:
   96 partitions, complementing existing January and final-October partitions.
   This makes a continuous requested stock window; options floor remains scoped
   coverage work. All sessions/extended observations are retained before filtering.
3. Option discovery across the **0–5 DTE** expiration dates for November 29, 2024
   (early close) and April 4, 2025 (busy market), both statuses/all three ETFs.
4. Deterministic nearest-strike call/put transport strata at targets 0/1/5 within
   actual 0–5 DTE, deduplicated across targets. Full-day option bars and opening
   30-minute trades. Selection uses only fresh stock/discovery responses and is
   not historical strategy eligibility or a complete option-demand census.

Retain each raw plan's 128-GET/30-minute invocation ceiling, 512-MiB root ceiling,
32-MiB page ceiling and serial 60-GET/minute cap. At most four bounded invocations
for the stock expansion and two each for discovery/options in this revision;
unfinished work remains explicit. Normalized roots cap at 2 GiB and two hours,
with disk >=max(100 GiB,20% total), RAM >=max(2 GiB,20% physical) plus 1 GiB parsing
allowance. One serial reader/writer; future parallel compute uses the autosizer.
Use the measured bootstrap density as a preliminary budget, then report actual
requests, bytes, rows and peak RSS. Preserve original roots, no recapture of
already collected stock months. No global bulk options campaign or training.

Completion for this milestone: v4 scope/guards tested and sealed; declared
expansion partitions captured or explicitly unfinished; all completed selected
inputs normalized with row/hash reconciliation, real session/missingness reports
and resume verification. Full option/context history, features, execution,
integrated pilot and input/dataset/model freezes remain later gates.
