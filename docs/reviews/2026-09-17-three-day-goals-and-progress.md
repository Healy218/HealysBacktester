# Three-day goals, progress and remaining work

**Review period: September 15–17, 2026. Status: paused for the user's review.**

**V7 is not ready to freeze, build at full scale, or train.** We have completed
substantial data preparation and software components, but have not demonstrated
the complete path on the full requested universe. No full V7 training dataset or
trained V7 model exists. My earlier statements that we were “close” overstated
what the evidence supported.

This report separates **implemented code**, **checks on selected data**, and
**completed full-universe work**. They are different levels of completion.
It is based on the current TODO, handoffs, dated reviews, Git history, saved
readiness report and the final test log. It is not a new audit campaign.

## 1. The goals we were trying to accomplish

| Goal | Agreed outcome | Current verdict |
|---|---|---|
| Make V7 ready to train | A reproducible, executable pipeline for the agreed history, universe, strategies, features and option behavior, with the data and resource checks needed to launch it | **Not achieved** |
| Establish the correct V7 data scope | March 15, 2022–September 14, 2026; Alpaca stock data, Massive options, no OTC, and historical membership rather than today's ticker list | Scope and major inventories completed; remaining identity and price-history exceptions prevent full admission |
| Correct option pricing and loss exits | Arithmetic bid/ask midpoint for paper prices; 7.5% option-premium stop for V6 and 12.5% for V7; retain strategy exits; ITM expiry exit 15 minutes before regular option close | V6 change deployed and an actual exit checked; V7 implementation exists but full historical labels have not been built |
| Preserve the running V6 experiment | Keep its existing model/portfolio intact while improving the authorized pricing behavior and investigating alerts | Preserved, but recurring quote-monitoring errors mean it is **not operationally healthy** |
| Keep the work within the agreed limits | Four outer workers, one inner thread, 100 GiB free-disk reserve, and a 250 GB acquisition ceiling rather than a storage target | Controls implemented; full build/training feasibility has **not** been demonstrated |

The V7 scope is 20 strategy families, 2,817 registered variants across each of
1/5/15/30-minute signals—11,268 variant/timeframe combinations—and all 222 model
columns, including the 13 TradingView scopes and 10 option-tick features. Actual
option expiry must be 1–9 calendar days away, with selection targets of
1/2/4/5/7 days. Portfolio evaluation must share five slots, the 10% premium cap
and one-symbol limit across timeframes. The earlier requirements also include
funded physical delivery and observed Alpaca stock liquidation where expiry
cannot be resolved by the specified option exit.

BBBY, FRC, REV and SI were excluded entirely under the no-OTC instruction, without
replacement or reranking. No move to another stock-data provider is pending.
External TradingView/Pine comparison remains explicitly deferred; local tests
do not establish that external parity. These scope decisions are not requests
to add more features or research projects.

Sources: [V7 specification](../specs/MULTITIMEFRAME_RESEARCH.md),
[active inputs](../specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json),
[option policy](../specs/V7_OPTION_RISK_20260916.json).

## 2. What we did over the three days

| Date | Main work completed | What that did not finish |
|---|---|---|
| September 15 | Completed base acquisition; moved active data to March 15; rebuilt membership and contract inventories; implemented all-timeframe strategy/feature adapters, quote replay, roll/shared-portfolio and funded-expiry components; added bounded storage/fold readers and explicit readiness checks | A complete full-universe feature/label dataset or executable training campaign |
| September 16 | Applied no-OTC exclusions; built full raw daily stock data, daily option surfaces, dated sectors and listed-identity histories; reconciled corporate actions; connected reviewed cash events to causal calculations; added train-only preprocessing and initial model trials; repaired authorized midpoint pricing and developed option-risk changes | Full action/identity admission, complete daily market context, full option-path capture, and production assembly |
| September 17 | Verified/deployed the option-premium risk policy; built and independently checked compact AAPL proposals across all timeframes; generated actual proposal-based entry-feature quote/trade requests; investigated V6 alerts; implemented the missing proposal-to-dataset assembly connection | Production execution of that assembler with all real inputs, full funded-expiry labels, full resource validation, or V7 training |

The September 17 assembly implementation is currently **uncommitted working-tree
code**, retained for review. It has passed the full regression suite but has not
run a full real-market build. The latest committed main revision is `ba66543`,
which covers the earlier entry-feature demand milestone.

## 3. The original TODOs, completed work and remaining TODOs

### A. Historical universe, stock data and identity

**Required:** identify the correct security behind each ticker on each date,
retain historical membership and aliases, and provide the required Alpaca stock
history without OTC substitutions.

**Done:** the current history contains 591 securities, 593 tickers and 1,129
sessions. We built 667,239 security/session history rows. There are stock bars
in 339,581 of 339,640 eligible sessions. The 59 zero-bar sessions have retrospective
merger, successor or halt explanations. We resolved dated rename overlaps and
retained explicit missing and ambiguous cases.

**Remaining:** resolve the 186 eligible identity/source mismatches and complete
held-position treatment across relevant lifecycle changes. Confirm the effect
of explained missing sessions on actual feature and execution paths. The bar
count proves session presence, **not a bar in every minute or complete execution
coverage**. An explanation for absent data is not automatically permission to
trade through it.

Evidence: [security history](2026-09-16-v7-security-history.md),
[no-OTC preparation](2026-09-16-v7-no-otc-preparation.md).

### B. Corporate actions and causal prices

**Required:** prevent future-adjusted prices, ticker reuse, splits, distributions
or reorganizations from corrupting historical features and execution prices.

**Done:** captured and reconciled 10,380 provider records into an inventory
including 5,030 exact symbol/day cash-or-split groups. Implemented causal price
reconstruction and action-aware features. Compiled 19 reviewed cash events:
18 Apple distributions and one Devon correction. The Devon review corrected a
real disagreement: the total distribution was $0.44, not an indiscriminate sum
of repeated $0.22 provider records.

**Remaining:** 10,340 provider records remain unconsumed by that reviewed-event
compiler. **That is not 10,340 distinct events or proof that every record is
wrong**; duplicates and different action categories are included. We still lack
a scalable, completed admission path for the remaining ordinary events,
combined actions, spin-offs and continuity/no-event intervals. Full market
context also depends on SPY's 36 unresolved provider cash-action records.

This is one of the largest unfinished workstreams. A complete inventory has not
translated into a complete usable adjustment history.

Evidence: [action inventory](2026-09-16-v7-action-inventory.md),
[cash-action integration](2026-09-16-v7-cash-action-integration.md).

### C. Daily, market and sector context

**Required:** supply causally available volatility, option-surface, market,
beta and sector inputs to every eligible model row, with explicit initial
warmup and missing observations.

**Done:** built 2,966 raw daily stock shards and all 1,129 daily option surfaces.
Reconciled their eligible-session joins. Built dated sector records for all
339,640 eligible sessions, preserving explicit unknown sectors. Implemented
causal daily returns/context without silently filling missing prices. Rebuilt
relevant derived inputs when execution policy bindings changed.

**Remaining:** produce the complete causal daily/market context from admitted
identity and action histories, including SPY, and connect it to every production
feature row. Raw daily data and surface files alone are not the finished daily
feature dataset.

Evidence: [raw daily build](2026-09-16-v7-full-stock-daily.md),
[option surfaces](2026-09-16-v7-full-surfaces.md),
[causal daily calculations](2026-09-16-v7-causal-daily.md),
[sectors](2026-09-16-v7-sectors-training-inputs.md).

### D. All strategy variants and 222-column feature rows

**Required:** evaluate every registered variant on each timeframe, preserve its
identity, apply dated entry eligibility, and compute the full feature schema.

**Done:** all 20 family adapters and the 222-column contract exist. A real AAPL
March 15–May 10, 2022 run produced 757,595 proposals across all 11,268 combinations.
Every reconstructed proposal field matched a fresh replay from the stored
signals. The proposal payload fell from approximately 807 MB in repeated JSON
to 9.90 MB in typed Parquet, a 98.77% reduction for those same rows. Completed
resume preserved all 736 receipts. The stored-row adapter was checked against
direct causal calculations, including action-boundary moving averages.

**Remaining:** run and admit the full history and universe with their real
context inputs. The AAPL result is meaningful integration evidence, not a
completed full-universe build. Cumulative storage and full-scale compute costs
are not established by that single-window result.

Evidence: [compact proposals and row joins](2026-09-17-v7-compact-proposals.md).

### E. Option data demand and capture

**Required:** obtain only the option quotes/trades actually required for feature
windows, purchases, minute marks, exits, rolls and expiry handling.

**Done:** built contract-selection and quote-archive components. The real AAPL
proposal inventory now yields 81,395 target selections, 197,020 feature links,
55,126 distinct requests and 107 contracts. Six bounded export files reduce to
7,472 capture intervals, representing 603.15 aggregate contract-hours per tape.
Selections, clocks and export coverage were independently checked.

**Remaining:** these are **pre-entry feature requests only**, and these newly
planned windows have not been downloaded. Entry fills, held minute marks,
exits, rolls and physical-delivery requirements must be combined with them.
Dated option-class hours and contract references must accompany the relevant
paths. Then capture only the specifically missing data and verify completeness.

The acquisition ledger at this pause is **63,043,400,695 bytes used of
250,000,000,000**, with no outstanding reservations. Filling the remaining
capacity is not a goal, and available capacity does not prove capture feasibility.

Evidence: [actual entry demand](2026-09-17-v7-entry-demand.md),
[quota ledger](../../nn_meta/data_v7/quota.json).

### F. Execution, expiry and portfolio accounting

**Required:** apply the chosen midpoint pricing, costs and option-premium stops;
retain strategy exits; close ITM expiries at the chosen cutoff; handle unresolved
expiry through the agreed funded physical path; reconcile shared capital.

**Done:** implemented midpoint replay, separate costs, option stops, roll retries,
explicit missing/unfilled outcomes, dated standard-contract checks, shared
portfolio components, funded stock-delivery accounting components and Alpaca
stock quote capture/replay. V6's authorized pricing/risk amendment was deployed.

**Remaining:** connect dated class hours, official exercise references,
deliverables, settlement calendars, funding and observed stock liquidation to
the actual V7 label/portfolio build. Validate all relevant outcomes and full
cash reconciliation together. The current option replay still leaves failed
expiry liquidation unresolved; the existence of a separate physical ledger
does not mean those two paths are fully integrated.

Evidence: [training preparation](2026-09-15-v7-training-preparation.md),
[stock quotes and settlement](2026-09-16-v7-stock-quotes.md),
[midpoint amendment](2026-09-16-midpoint-paper-pricing.md).

### G. Assembly, folds and training

**Required:** turn proposals, real features and option outcomes into bounded
training inputs; retain full label horizons; apply purged chronological folds;
run the declared model/objective comparisons without leakage.

**Done:** factorized storage, bounded fold readers, train-only preprocessing,
finite-value checks and model reload/resume components exist. Twenty-one initial
constant/GBT/neural objective/seed trials were declared and exercised as
components. The newest builder now joins stored proposals, observed tick/replay
adapters and all 222 columns into resumable shards and an input index for the
fold reader. Its integration tests use explicitly fictional captures.

**Remaining:** supply its real complete daily/session/capture inputs, integrate
funded physical outcomes, build the actual campaign data, and connect the full
trial runner, baselines, calibration/threshold/weight choices and multiple-testing
accounting. The latest builder has not produced the requested full dataset.
Full training has not started.

Evidence: [model components](2026-09-16-v7-model-trials.md),
[new assembly implementation](2026-09-17-v7-dataset-assembly.md).

### H. Resource and final readiness checks

**Required:** demonstrate that the connected workload fits disk and memory,
recovers correctly, respects worker limits and coexists with V6; then pass the
complete readiness gate.

**Done:** bounded component readers, thread limits, disk guards, checkpoints and
small real-data performance measurements exist. The latest complete software
suite passed **1,976 tests and 18 subtests**, with 18 warnings, in 122.33 seconds.

**Remaining:** measure the integrated real workload, total storage, LightGBM's
binned-dataset memory, restart recovery, swap behavior and V6 coexistence at
representative scale. Passing unit tests is not this resource gate. We do not
have a supported full-run duration estimate.

The latest saved readiness report passes three foundational checks: active
inputs, rebuilt membership and coverage inventory. **All eight substantive
stages remain unpassed:** lifecycle, causal prices, daily context, quotes,
physical execution, assembly, trials and integrated resource checks. This does
not mean no useful work exists in those stages; it means none has sufficient
full-scope completion evidence.

Evidence: [saved readiness report](../../nn_meta/validation/v7-readiness-20260917-entry-demand.json).

## 4. V6: what was fixed, and what remains broken

The pricing/risk correction is real. The saved FIG position entered at midpoint
$1.485 and exited at $1.37 approximately 3 hours 11 minutes later. That is a
7.7441% premium loss and approximately 8.0205% net after the separate modeled
costs. It crossed the requested 7.5% midpoint stop; this particular exit was not
an immediate spread-only loss.

The recurring attention alert is a separate unresolved operational issue. The
inspected AMPX contract lacked an acceptable quote within the configured
30-second freshness window. The current control flow withholds all new entries
when held-position monitoring is unresolved. Other existing positions may still
exit when their quotes are available. A failed quote check also occurs before
that position's normal strategy-exit evaluation, which deserves review.

For September 17, the local ledger contained six entry notices and four exits.
The server recorded all ten as `sent`. That confirms notifier acceptance, not
that the user saw each alert on the phone. I did not establish a missing-buy
queue bug, and I did not fix the recurring quote problem during the investigation.
V6 is partially operating, not verified healthy. No broker orders are involved.

**Remaining V6 TODOs for discussion:** decide the intended behavior when one held
contract lacks fresh quotes; preserve pending exits and signal evaluation;
make the health alert explain the specific position and blocked operation;
verify user-visible delivery if notices still appear absent. No additional
runtime changes are authorized by this report itself.

## 5. Where we have been spinning our wheels

1. **We built and checked many pieces before closing the production path.** The
   assembly consumer connecting those pieces was only added on September 17.
   Finding integration failures earlier would have given the work a clearer order.
2. **Data review expanded faster than usable input admission.** The action
   inventory is comprehensive, but only 19 reviewed events reached the compiler.
   Repeating individual evidence investigations is not a demonstrated scalable
   route to finishing thousands of remaining records.
3. **Progress updates emphasized local successes.** More tests, compressed files,
   successful captures and passing AAPL examples were reported while the same
   eight full-scope stages remained open. They were useful results, but they did
   not justify saying training was close.
4. **V6 interruptions consumed attention without a stable operational resolution.**
   The midpoint repair addressed a real requested behavior. Repeatedly diagnosing
   quote failures did not establish a durable policy or restore healthy operation.
5. **Some rework was necessary, but it did not excuse the delivery gap.** The date,
   no-OTC and pricing clarifications legitimately changed artifact bindings. I
   should have made their impact explicit and kept a clear path to a runnable build.
6. **We have not resolved full-scale feasibility early enough.** Small bounded
   readers do not prove the whole dataset or model's memory/storage requirements.
   That uncertainty should have been visible before describing the task as nearly
   finished.

My assessment is that there has been substantial useful work, **and** the work
has been poorly converged on the requested deliverable. Resetting context alone
would not correct that. We need to review the required admission rules, the
remaining integration path and the evidence needed to close each item.

## 6. Consolidated remaining TODOs before the goal is finished

These are the outstanding deliverables, **not instructions to resume work now**.

| Order | Remaining deliverable | Evidence that would close it |
|---|---|---|
| 1 | Complete usable identity/action histories under an agreed admission policy | Every relevant security/session/action has an explicit resolved treatment, consumed by the actual feature and held-position paths |
| 2 | Produce complete causal daily/market context and full feature/proposal stores | Full scoped census with correct availability, warmup, sectors and all registered variants; no substituted fixture inputs |
| 3 | Complete actual option-path demand, dated hours/reference inputs and targeted captures | The union covers required entry features, purchases, marks, exits, rolls and applicable stock-delivery observations within the acquisition budget |
| 4 | Finish integrated option/physical/shared-capital execution | Real captured cases and full accounting demonstrate midpoint stops, signals, expiry, funding, settlement and liquidation without invented outcomes |
| 5 | Execute full data assembly and connect folds/trials | All required 222-column rows and outcome records reconcile; label horizons and fold purging are correct; the complete predeclared campaign is runnable |
| 6 | Establish resource and recovery feasibility | Measured memory, disk, throughput, restart and coexistence evidence supports the proposed full run |
| 7 | Pass the complete readiness gate and notify the user | An inspected full-scope report passes every required stage; only then may we claim V7 is ready |

Some work overlaps between these rows. We should discuss that dependency order
before resuming rather than treating this as seven more independent projects.
A reasonable review question is whether any implementation-created requirement
has expanded beyond the agreed research objective; any proposed change must be
explicit, with its effect on correctness and scope explained.

Separate or deferred work—external Pine comparison, additional model families,
new feature groups, broader issuer/news collection, dashboard deployment and the
year-end maturity scorecard—is not an excuse to delay this V7 deliverable.

## 7. Pause state

- V7 development, acquisition, builds, tests and training are paused for review.
- The latest full test process exited successfully; no V7 Python job was running
  in the host process check. Existing V7 acquisition/pilot units were inactive or
  terminal failed records, not running work.
- No V7 or old short-DTE research timer remains scheduled. The obsolete
  `healys-v6-short-dte-20260914-now-progress.timer` was disabled and stopped.
- Pre-existing V6 paper operation and unrelated production services were left
  unchanged. Stopping research does not silently abandon open paper monitoring.
- Existing data and code are preserved. The latest assembly implementation and
  its six tests remain uncommitted for review. No extra source deployment,
  capture, build, training run or notification resend was started for this report.
- Do not resume the V7 goal automatically from older handoff instructions.
  The user's explicit next instruction after this review is required.
