# V7 readiness — integrated pilots passed; full admission still open

Updated September 15, 2026, after 21:15 UTC. The user requested **all four V7 readiness workstreams**. Continue them; this task is **not complete**. Do not launch the full freeze/build/training campaign until the gates pass. No subagents are authorized. Use four bounded computation workers and the shared **250 GB decimal acquisition cap**. Preserve the activated V6 runtime and unrelated dirty files. No test notifications.

## Start here

The implementation review is [docs/reviews/2026-09-15-v7-readiness-implementation.md](docs/reviews/2026-09-15-v7-readiness-implementation.md). Its top section supersedes older pending-implementation statements below.

Pushed commit **22a108e** includes complete feature rows, dated contract checks, quote rolls/censoring, shared allocation, provenance guards and integrated pilots. Earlier checkpoints da66931, b9e995b and 6da5c8f are pushed.

Latest full regression: **1,707 tests +18 subtests**, 82.42 seconds, /tmp/healys-v7-integrated-final-tests.log. A clean archive of 22a108e passed **84 V7 tests**, 17.13 seconds, /tmp/healys-v7-clean-integrated-tests.log. Clean checkout: /tmp/healys-v7-repro-22a108e.

New work after that commit:
- Paced Massive corporate-action retries; missing option-day retry script. Both completed successfully.
- Alpaca corporate-action capture script and raw/adjusted daily-factor diagnostic.
- Two new adjustment-diagnostic tests passed.
- TODO, this handoff and the review need a scoped checkpoint commit. Do not stage unrelated TODO edits; /tmp/v7-integrated-todo.patch contains only our checklist change.

## Current jobs

- **healys-v7-adjustment-audit-20260915**: running all 3,714 stock pairs. Output nn_meta/validation/v7-adjustment-diagnostics-20260915. Four workers, 7 GiB cap, swap disabled. At the last check: 140 pairs, 31,194 dates, zero incompatible dates. Do not edit scripts/audit_v7_adjustments.py, nn_meta/v7/adjustments.py or coverage.py while this runs.
- **Alpaca corporate-action capture**: requested through the escalated foreground call; check its completion/output nn_meta/data_v7/alpaca-actions-20260915. Covers process dates 2021-01-01 through 2026-09-15, all US action types, data_quality=all. This is reconciliation evidence, not proof of historical publication availability.
- Stock supplement, supplement audit, hardened base audit and paced Massive action capture are complete.

## Acquisitions and audits

Fixed research window **2022-03-07–2026-09-14**, with 2021 as warmup only. Plan nn_meta/research_plans/v7-20220307-20260914/plan.json is huge; parse selected fields. SHA: 9a5c1da4c7563471c6bfd73fd30e5eb179c6cb62d497d64c1545f468c7974b09.

| Artifact under nn_meta/ | Current evidence |
|---|---|
| data_v7/base-20260915r4 | All 8,284 acquisitions present, including newly available Sep14 option day/minute files |
| validation/v7-full-audit-20260915r2 | Hardened receipt checks: 4,142 jobs, including 2,712 stock pairs and 1,430 option days |
| data_v7/historical-stocks-20260915 | 167 additional roots, 2,004 tasks, zero failures |
| validation/v7-supplement-audit-20260915 | All 1,002 pairs audited; 81,553,702 raw minute rows; matching timestamps |
| data_v7/corporate-actions-20260915 | 7,113 splits and 258,084 dividends captured from Massive |

The base has 275,110,957 raw minute rows. Base missingness: 135 empty pairs and 159 nonempty pairs with zero-observation sessions. Supplement missingness: 115 empty pairs and 92 nonempty pairs with zero sessions. These require listing, alias or no-trade attribution; empty is not automatically valid prelisting history.

Supplement audit took 40.02 seconds, 5 GiB peak, no swap. Massive action capture completed after 13-second pacing (service healys-v7-actions-20260915r3, 11m52s, 135 MiB). HTTP429 partials remain preserved and charged. Last quota was about 60.13 GB before later work. **Never reinitialize quota while a capture is active.**

## Price basis: unresolved, with a concrete rounding explanation

Large ratio spreads in SBET and FCEL appear consistent with cent rounding after reverse splits:
- SBET 2022-12-20 20:54 UTC: raw [.2608,.2624,.2607,.2607], adjusted [31.30,31.49,31.28,31.28], later cumulative split factor 120.
- FCEL 2024-10-08 10:48 UTC: raw [.3515,.3515,.3505,.3515], adjusted [10.55,10.55,10.51,10.55], later factor 30.
- SPY also shows adjusted cent rounding.

The running diagnostic intersects all OHLC constraints for a common factor per New York date, with declared adjusted rounding tolerance .005000001. Compatibility is only evidence for that explanation; it does **not** establish the factor's availability or future-action invariance.

Today's rounded adjusted series and scalar minimum_tick=.01 remain a causal feature concern. Alpaca adjustment=all also includes spin-offs. Its current /v1/corporate-actions endpoint supports spin-offs, mergers, name changes and reorganizations; these records may help both price and identity attribution. Current-share cumulative factors from Massive must not be used directly as historical PIT inputs.

## Security identity

Monthly masters: data_v7/security-master-20260915 (69 complete captures). Dated/event references: data_v7/reference-20260915 (12,692 responses).

Provisional universe **validation/v7-identity-universe-20260915r2** has **598 ticker names, 596 identities, 16,577 membership rows**. It resolves 424 transition months. Seven observed option dates still lack FIGIs:
- AESI: 2023-10-02.
- NUSI: 2024-11-08.
- BEPC: 2024-12-20, 23, 24, 26, 27.

None is a candidate ticker, but their ranking impact must be proven absent or the identities resolved. identity_boundaries_verified remains false. Ninety successful responses lack FIGIs overall; most have no relevant option observations.

Current 449-name list: docs/specs/v7-tickers-20260915.txt. Historical candidate list: validation/v7-identity-universe-20260915r2/symbols.txt. The old static-alias 622-name draft is superseded.

**BITF→DRAM is invalid** (Bitfarms versus Roundhill Memory ETF). **FIG was reused** (Simplify ETF versus Figma). Thirty-six candidate roots changed FIGIs. Still needed: per-security price stitching, listing/gap attribution, identity-bound sector mapping and protection against intramonth identity cycles. Do not modify frozen V6 numerical assumptions incidentally.

## Feature and pipeline evidence

All 13 TV scopes, 20 strategy families and 2,817 variants per timeframe are implemented: **11,268 per ticker across 1/5/15/30 minutes**. External Pine comparison remains explicitly deferred. V7 uses minute opening-range/VWAP and declared local HTF assumptions (240m/720m/2D).

The row adapter has **222 columns**: original 164 groups, four timeframe fields, 48 numeric parameter fields and six setup identities. MA features use each variant's windows. Daily/tick/identity/availability checks are implemented.

Daily context uses raw spot for IV, the separately declared adjusted return basis for RV/beta, fixed .0425 rate/.012 dividend-yield baseline proxies, and next-session-open availability. Missing captures cannot be hidden by forward fills. Real SPY daily artifact: validation/v7-daily-spy-20260915, 300 sessions.

Integrated pilot **validation/v7-pipeline-pilot-20260915**:
- All 11,268 variants; **101,993 proposals** retained.
- Counts for 1/5/15/30m: 76,071 / 16,333 / 6,587 / 3,002.
- First chronological proposal per family/timeframe, independent of outcomes: 72 full feature rows; 70 completed observed labels and two censored.
- Families with no proposals remain in the tested catalog.
- Four workers, 247.6 seconds, 4.3 GiB peak, swap disabled.
- Expanded source/runtime/input manifests and mutation guards passed.

Proposal simulation retains the existing trend50, stops5%, shorting and nominal-capital guards. Open trades remain explicitly censored. No winner filter or 2,000-event cap applies. This is plumbing evidence, not strategy performance.

**Storage remains open:** the week has 37,711 distinct decision/exit/side paths and 2,509 feature windows before DTE targets. A naive five-target, 222-column float32 expansion needs 452,848,920 bytes before identifiers/labels. Implement factorized features/parameters/labels and bounded training assembly. Do not extrapolate SPY blindly to the whole universe.

## Quote, execution and shared-portfolio evidence

Bounded chain **validation/v7-chain-bounded-20260915**: 22,113,664 contracts, 8,702 roots, 99.32 seconds, 3.6 GiB, no swap. Exact external-sort comparison with the old catalog passed; canonical SHA af3cf5b1c1a4b0618eaf9c332c67eebd2e181d3d4cc08681b92d05bfb50f9944. **It lacks the newly downloaded Sep14 day; update before full admission.**

SPY quotes data_v7/spy-week-quotes-20260915: 27,864 shards, 72,894,383 records, 1.321 GB, 148 contracts and 516 contract-days. All dated references in data_v7/contract-reference-20260915 are now enforced: 100 shares, American exercise, no additional deliverables, matching contract identity. All four tick windows use causal seeds and the existing condition-209 policy. This is a pilot superset, not full-universe coverage.

Replay policy: observed ask/bid, one-second latency, 60-second deadline, 30-second mark age, .001 fee plus .0005 slippage each side, fractional paper allocation, actual 1–9 DTE on every purchase. Minute marks, expiry liquidation retries, rolls after actual sale fills, reinvested proceeds, maximum 60 rolls. Missing captures and observed-unfillable markets are separate statuses.

Fixed put pilot validation/v7-real-roll-put-20260915r2 completed an observed expiry roll and final exit. Matching call v7-real-roll-call-20260915r2 has complete capture but no eligible expiry bid and stays unresolved.

**Pending async user question:** keep unresolved/block (recommended default), explicitly abandon via do-not-exercise, or implement physical exercise/stock delivery. No reply received. Do not assume abandonment/exercise. Historical option-class hours are still unverified; the SPY +15-minute close and -15-minute liquidation buffer are provisional pilot rules.

Shared portfolio: five slots, 10% equity, one symbol across timeframes, causal score/stable-ID ranking, pending cash reservations, separate roll proceeds, and paused new entries when held marks are unavailable. Observed exits still run. Future completion/returns never filter entries.

Real validation/v7-portfolio-pilot-20260915 used all 72 sample paths and constant zero scores. Captures and valuations are complete; eight proposals closed and one remains censored/open. Unit tests cover multiple symbols, pending fills, stale equity, rolls and dot/OCC spelling.

## Next concrete work

1. Finish identity/ranking impact, listing/alias histories and price-vintage policy using the action evidence.
2. Complete factorized full-history row/label storage, bounded training assembly and any necessary shared primitive optimization; cover all five target DTE choices.
3. Resolve dated option hours/expiry policy; inventory and measure full-universe quote/metadata demand under 250 GB; run broader and full-history resource pilots.
4. Bind all source/runtime/data/policies, pass complete-universe gates, then launch the full campaign.

Frozen evaluation declaration docs/specs/V7_EVALUATION_20260915.json: expanding 2024H2/2025H1/2025H2 validation, 2026-01-01..09-14 final evaluation, ten-session embargo, train-only fitting and completed-label horizon purging. Known periods are revalidation. SHA f03272ee3545b08c2dbb4deb2d92da3ad32b3e323923e9ff630ef6f94a119ae3. Amend with a new version; do not rewrite.

## V6 and unrelated work

V6 saved status /home/healy/Coding/HealysV6/nn_meta/live/v6_server/status.json at **2026-09-15T21:15:05Z** says data_through=2026-09-14, status=idle, phase=outside_market_hours, next_session=2026-09-16. Its saved data date advanced; intraday trade behavior was not audited. No V6 numerical changes or test notifications.

Frozen home runtime /home/healy/Coding/HealysV6 is d6660af; server runtime /home/mrhea/HealysV6. Dashboard/evidence-journal deployment is still outstanding. Preserve unrelated V6 files/docs. Git deployment only, never scp.
