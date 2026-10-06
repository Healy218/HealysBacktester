# ETFE exact window demand and historical input checks — October 6, 2026

**The computable-history signal and entry-window census is complete within its
declared scope. ETFE-0 admission, complete strategy demand and realized holding
paths remain open.** All market data remains fresh Alpaca for SPY/QQQ/VOO,
through October 2, 2026. Purchases and rolls remain 0–5 calendar DTE; daily
context spans 1–45 DTE. No signal, contract, fill or label is admitted by this
measurement.

The demand contract and bounded limits are in
[ETFE_WINDOW_DEMAND_20261006](../specs/ETFE_WINDOW_DEMAND_20261006.md).
Selected computation receipts are under
`nn_meta/validation/etfe-window-demand-20261006-r0/`; exact decisions and the
independent clock audit are under
`nn_meta/validation/etfe-exact-windows-20261006-r0/`. The 36-request bounded
Alpaca check is under `nn_meta/data_cache_etfe/alpaca-fresh-window-checks-20261006-r0/`.

## Computable-history census

The context inventory contains **137,080** exact regular-session request
batches and **13,609,133** returned-contract/session memberships at 1–45 DTE.
That is 5,288,907,030 requested symbol-minutes before response sparsity and
pagination. It covers the current 452,347-symbol discovery census; it does not
prove historical listing completeness.

All **180** family checkpoints and **25,353** ticker/variant computations
completed against the collected raw stock history. The packed channels reconcile
to 25,848,975 / 41,836,876 / 24,448,153 / 25,873,068 memberships. SPY and QQQ
retain their complete expected-minute signal grids. For VOO, the first missing
minute is May 22, 2024 at 16:39 UTC. Recursive state after that point remains
unresolved; no reset or fill was inserted. This is a conservative state mask,
not a claim that every finite-window field needs recursive history to the end.

Factored exact windows cover **4,311,060** decision clocks and
**151,005,384** logical 0/1/5-DTE links. The nine scopes pass an independent
decision-key, membership-total, signal-clock and interval-bound audit. At each
signal `t` with timeframe `m`, feature acquisition is `[t-(m+1)min, t-1min)`
and the entry reference is `[t-1min, t)`. Same-day first observations are not
eligible prior-date candidates. Selection remains explicitly unresolved when
no earlier observation exists or when dated eligibility/terms are missing.

On currently selectable symbol identities, the signal feature/entry windows
reduce to 2,857 option-bar and 3,446 option-trade physical intervals. Reusing
only complete hash-verified windows leaves 2,678 bar intervals / 102,079 minutes
and 3,221 trade intervals / 98,828 minutes pending. These counts cover 0/1/5
targets. Conditional weekly 2/4 targets retain **93,915,652** unresolved logical
memberships for SPY/QQQ; they are not included in the physical candidate union.

## Acquisition-density and VOO checks

A finite density pilot selected four duration order-statistic windows per ETF
and route (24 option requests). It returned 513 option bars and 8,409 option
trades. Two trade windows were empty. The windows were deliberately chosen to
span duration ranks, not randomly; these observations demonstrate highly
uneven density and cannot estimate full-campaign totals. Exact 1–45-DTE context
remains an unusually large separate acquisition requirement.

Twelve three-minute SIP rechecks requested the missing VOO minute with the
preceding and following minute as controls. All twelve responses contained the
two neighboring bars and omitted the requested minute. This confirms those
timestamps were not returned by the fresh Alpaca SIP route in the recheck. No
VOO signal state was repaired and downstream recursive state stays unresolved.

## History and dated terms boundary

Earlier fresh Alpaca coverage returned no bars for any of 23,176 discovered
option symbols over January 1–17, 2024; January 18 at 09:30 ET remains the first
observed option bar in that tested inventory. This is a route/inventory boundary,
not proof of earliest possible listing, complete history, or usable research
start. Stock capture begins January 2, 2024. The fixed market end remains October
2, 2026. Missing pre-boundary or unavailable VOO observations are not synthesized.

Official Invesco tax-reporting data lists QQQ's March 18, 2024 ex-date with an
April 30 payable date (Primary ICI Report, row 1725; workbook hash
`79f40d466b77539c4579d90bb1d0f15521cb01f26f6450f0dd3b88185ac4dd0f`). This
resolves the economic payable term retrospectively. The report is labeled
January 21, 2025; it does not establish what the model could know in March 2024
or settle the broader action-revision timeline. The original Alpaca values stay
preserved and are not backdated from this later issuer file.

Contract clocks/economics, 1SPY interpretations, pre-transition settlement,
class/ETF status, historical SIP size units, official exercise references and
original/revised action availability remain separate ETFE-0 blockers.

## Execution and next boundary

There are **zero realized holding paths**. Synthetic scheduler/lifecycle tests
validate component behavior only. A selected historical candidate and actual
execution receipt are required before an option-held path can be extended to
exit, roll, exercise, assignment, stock liquidation or settlement. The tested
frontier kernel defines requests at those states but has not traversed a real
ledger. The measured exact-window union therefore excludes future path requests.

The bounded compute restart made no new GETs and preserved the 49-file signal
prefix captured before continuation; all 180 family receipts and nine exact
scope outputs now verify by hash. The six-year complete signal census took about
11.4 minutes of resumed compute, peak RSS was 4.09 GiB, and output stayed within
the declared 4 GiB output bound. The independent audit confirms 4,311,060
factored decisions and no admitted entries. Full ETFE regression was not rerun
for this scoped computation.

The source-bound exact-option capture plan groups the post-pilot physical union
into **3,036 requests**: 1,369 option-bar and 1,667 option-trade jobs. The first
four resumable 128-GET runs reached **512 terminal option-bar jobs** and
normalized all **27,073 occurrences** with an independent raw-to-Parquet audit.
The next 857 bar and 1,667 trade jobs remain queued. The capture plan is ordered
by route, so no trade jobs were included in those first four runs; the separate
24-window density pilot is the only newly captured exact-window trade sample to
date. Raw capture uses 9.64 MB, normalization 512 partitions / 27,073 rows,
and neither artifact is admitted as model input.

**Next:** resolve dated contract/action/settlement evidence and the scoped
history boundary; retain the twelve VOO gaps as unresolved; then derive holding
windows only from dated eligible selections and actual execution receipts.
Reconcile a representative acquisition budget before scheduling the remaining
5,899 pending exact intervals. Input freeze, scientific admission, training and
evaluation remain later ROADMAP gates.
