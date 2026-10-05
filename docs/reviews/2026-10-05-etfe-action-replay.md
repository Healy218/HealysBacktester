# ETFE action replay and distance to freeze/train

Completed **ETFE.provider-action-replay** for four fixed control days, with
independent raw-event reconciliation and an actual restart. The selected run
provides **one matched pre-effective action witness among 35 records**. This is
useful timing evidence, but input admission and dataset freeze remain open.
[Machine receipt](2026-10-05-etfe-action-replay.json),
[successor contract](../specs/ETFE_ACTION_REPLAY_V2_20261005.md).

## What is left before training

| Step | Current evidence | Remaining exit requirement |
| --- | --- | --- |
| Features | All 221 component fields and 221 masks joined for 458,133 January pilot events | Full-history generation, required dated inputs and feature admission |
| Inputs | Fresh stock window, bounded January option surfaces/trades and action observations | Complete required option/context demand and capture, usable-history boundary, dated contract/actions/session/source evidence |
| Execution and labels | VWAP reference and selection/0–5 DTE guards implemented | Full ledger, partial exits/stops, settlement/physical paths, terminal outcomes and real-data reconciliation |
| Integrated pilot | Individual capture/feature/resource/restart studies passed | Capture → admitted features → execution → dataset → training smoke, measured resources and recovery |
| Freeze and train | Definitions and trial policy declared | Full dataset build, independent admission, frozen inputs/schema/labels/folds, then the declared training trials |

Feature construction is substantially implemented; the critical remaining work
is data admission, execution/labels and the integrated build. Neither a count of
passing tests nor one successful provider witness measures a completion percentage
or supports a training date. The next implementation task is the bounded execution
ledger component, with synthetic dated fixtures kept distinct from real admission.
Provider timing and full acquisition demand remain necessary work alongside it.

## Four-day replay result

| UTC day | Pages | Complete event occurrences | Unique events | Interpretation |
| --- | ---: | ---: | ---: | --- |
| 2024-03-14 | 1 | 0 | 0 | Welcome-only EOF; history coverage unknown |
| 2025-03-20 | 1 | 0 | 0 | Welcome-only EOF; history coverage unknown |
| 2026-03-19 | 1 | 0 | 0 | Welcome-only EOF; history coverage unknown |
| 2026-09-17 | 10 | 45,559 | 41,730 | Complete requested transport; retention still unverified |

The September replay contains **five SPY events**: an insert at
`2026-09-17T21:59:24.391802Z` followed by four updates, all before its September
18 ex-date. Native ID, symbol, ex-date and Decimal dividend rate match the fresh
REST action. The selected rate is 1.888834. This witnesses that provider version
before the effective date; it does not prove original company announcement time
or complete latest-as-of revision coverage at every later decision.

The other 34 action records have no matching pre-effective witness within these
four control days. They are not declared unavailable everywhere. Empty controls
do not establish retention bounds, complete action absence or a usable-history
start. All normalized inputs and model-admission flags remain unchanged.

## Precision rejection and recovery

Original r0 stopped when a response to `since=09:30:08.378721Z` began at
`09:30:08.378324Z`. The strict guard rejected the earlier events. Its seven GETs,
partial output, source snapshots and REJECTION receipt are preserved. No tolerance
was loosened and no old receipt was relabeled.

Successor r1 deliberately restarts at the beginning of the last complete event's
second, preserving inclusive overlap. Each returned event must satisfy the exact
new request bounds. **3,829 repeated occurrences** reconcile to identical event
IDs/payloads; all occurrences and partial raw blocks remain auditable. No event
is skipped by advancing the cursor beyond an equal timestamp.

An actual stop after four requests, including the first capped September page,
then resume preserved **twelve committed files** byte-for-byte. A separate,
line-oriented parser reconciled all raw events, overlaps, ETF fields/source links
and all 35 action-witness classifications. **210 focused ETFE tests passed**,
including fourteen new replay tests. Source-bound predecessors still verify.

Selected capture: **13 GETs, 15.63 seconds, 20,043,029-byte root**. Including the
rejected attempt: 20 GETs. All declared page/day/root/request budgets held. No
background process, new market-price data, labels, training or deployment.

Selected root: `nn_meta/data_cache_etfe/alpaca-fresh-action-replay-20261005-r1/`.
Plan SHA256: `50655f2359307cf90f5f087d66021fac139ba774724578e90ab20825dbdc65e2`.
Rejected root: `nn_meta/data_cache_etfe/alpaca-fresh-action-replay-20261005-r0/`.
[Evidence ZIP](2026-10-05-etfe-action-replay-evidence.zip): 68 metadata/source/
audit members and a SHA256 index of 20 raw payloads. Archived members and local
raw hashes were checked. ZIP SHA256:
`6b2c8c66a84b4b91564b8b8357dacdb7e6f9ac5c2a506bc7d892f5705c0063e6`.
