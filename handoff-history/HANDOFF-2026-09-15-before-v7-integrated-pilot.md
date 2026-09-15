# V7 all-four readiness workstreams — implementation in progress

Updated 2026-09-15T18:38:25.269577+00:00. User requested “let’s do all 1–4 for v7 now please.” Continue all four; **not complete**. Full-universe freeze/build/training remains gated. No subagents authorized. Four computation processes, shared 250 GB decimal acquisition cap, main checkout, preserve activated V6 and other dirty work.

## Pushed checkpoint

- `da66931`: tested source-port reuse/recurrences and bounded observation projections, prerequisites previously uncommitted. No V6 deployment/activation.
- `b9e995b`: V7 historical audits, all-timeframe adapters, reference captures, quote archive/cash ledger, evaluation policy and pilots.
- Detailed evidence and remaining gates: [readiness implementation](docs/reviews/2026-09-15-v7-readiness-implementation.md).
- Full regression: **1,682 tests +18 subtests**, 80.25s, `/tmp/healys-v7-readiness-final-r2-tests.log`. Earlier final attempt failed four tests from eager Polars initialization; chain import now initializes under the thread guard. Latest universe handling of captured-but-missing FIGIs has focused coverage; rerun affected tests after further changes.

## Completed data work and findings

Base root `nn_meta/data_v7/base-20260915r4`, fixed March 7, 2022–September 14, 2026; 2021 warmup only. 8,282/8,284 acquisitions: missing Sep14 option day/minute files. All 5,424 stock receipts exist. Full audit `nn_meta/validation/v7-full-audit-20260915` completed 4,141 jobs: 2,712 stock pairs +1,429 option days, 275,110,957 raw minute observations, all raw/all timestamps match. 135 empty pairs and159 nonempty pairs with some zero-observation sessions still need listing/no-trade/vintage attribution. Subsequent receipt-path hardening needs a new audit output to bind the latest source; preserve prior successful artifacts.

**Identity defects:** legacy BITF→DRAM is invalid (Bitfarms versus Roundhill Memory ETF, list2026-04-01). FIG ticker has both Simplify ETF and Figma identities. Do not alter frozen V6 numerical source. V7 uses explicit FIGIs, not static aliases. 69 monthly masters captured under `nn_meta/data_v7/security-master-20260915`. All dated transition requests completed:12,692 total response captures under `nn_meta/data_v7/reference-20260915` (including earlier overviews/events). 90 HTTP200 responses lack FIGIs; preserve these as unresolved evidence.

Rebuilt `nn_meta/validation/v7-identity-universe-20260915r2`:598 historical ticker names,596 identities,16,577 membership rows.424 transition months resolved, three still need identities on observed option days: AESI2023-10-02; NUSI2024-11-08; BEPC2024-12-20/23/24/26/27. None is in the598-name candidate list, but ranking impact or exact identity resolution must be established before full admission. `identity_boundaries_verified=false`. Original static-alias draft622names is superseded. Provisional598 list lives in the r2 output `symbols.txt`; current449 reference remains `docs/specs/v7-tickers-20260915.txt`.

## Strategy and quote pilots

`nn_meta/validation/v7-signals-pilot-20260915r2`: all11,268 variants,20families,1/5/15/30minutes, SPY2022-03-07..11 retaining all2021warmup. One-minute116,815bars,189.34sec,2,239,272KiBworkerpeak. Other timeframes21.9..50.9sec. 96TV+15base technical columns. Full model features/parameter-specific MA row values, adjusted-price vintage invariance, stop/trend-filter proposal timelines and labels are not yet assembled. V7context minute opening range/VWAP/localHTF assumptions isolated; externalPine parity deferred.

`nn_meta/validation/v7-chain-20260915`:22,113,664contracts/8,702roots from1,429days. Initial global grouping completed but used5GiBRAM+16.2GiBswap: resource gate FAIL. Source now disk-partitions grouping; unit exactness test passed. **Running full replacement** `healys-v7-chain-bounded-20260915.service`, output `nn_meta/validation/v7-chain-bounded-20260915`,64partitions,MemoryMax6G/High5G,SwapMax0,CPU100%,Nice15. Check completion, resource counters, and exact catalog equivalence before claiming success.

SPY quote plan `nn_meta/validation/v7-quote-plan-spy-20260915`:allminute selectors,bothrights,target1/2/4/5/7,19,500selections,148contracts,516contract-days. Complete capture `nn_meta/data_v7/spy-week-quotes-20260915`:27,864shards,72,894,383quote/trade records,1.321GB. Service `healys-v7-spy-quotes-20260915` finished. This is a pilot superset, not full-universe coverage. Raw quotes/trades obey original immutable Massive capture manifests.

All516 dated contract-day references captured `nn_meta/data_v7/contract-reference-20260915`; each reports shares_per_contract100,American,noadditionalunderlyings. **Next bind/validate this metadata in a loader before execution labels.** Pilot close extension15minutes is provisional explicit SPY policy; dated option-class session rules still need evidence. Full roll/exercise/expiryhandling is NOT yet implemented in an integrated replay engine.

Fixed four-contract volume sample `nn_meta/data_v7/quote-volume-pilot-20260915`:216shards,511,826quotes+6,731trades,9.55MB. Fixed one-hour plumbing replay `nn_meta/validation/v7-quote-volume-pilot-20260915/replay.json`:twoobservedfills,60/60causalmarks,cash/costreconciliation. Not strategy performance. `QuoteArchive` now reads adjacent verified shards with boundedLRU; missingcapture≠observedempty. `CashLedger` usesask/bid,actualfill-date1–9DTE,fractionalpaperfive sharedslots/10%equity,0.10%fee+0.05%slippage eachside on top ofspread; missingexitsstayopen.

## Evaluation declaration

`docs/specs/V7_EVALUATION_20260915.json` immutable declared16:18UTC:expanding2024H2,2025H1,2025H2validation; final2026-01-01..09-14;10sessionembargo;purgefullcompletedlabelhorizons;train-onlyfitting;knownperiodsexplicitlyrevalidation. Hash `f03272ee3545b08c2dbb4deb2d92da3ad32b3e323923e9ff630ef6f94a119ae3`. Do not rewrite; amendments getnewversion. No training launched.

## Next concrete work

1. Finish identity boundary resolution/ranking impact, then acquire supplemental historical598candidate roots absent from452basefetchroots under sharedquota. **Do not reinitializequota while anycaptureworker isactive.** Existing downloader main initializesquota; create a supplement runner using existing `acquire` with the initializedledger, or serialize initialization when allworkersidle.
2. Fullfeatureadapter:dailyoptionsurfaces/rawspot+adjustedreturns/SPYbeta,explicitproxy rate/dividendassumptions,contracttickfeatureswith existing209conditionpolicy,categorical/timeframe/parameteridentities,correct MAfast/slow perrow. Currentfullsuite164features includes96TV+10ticks. `nn_meta/option_tick_dataset.compute_feature_row` is timeframe-generic; old task declaration is15m-specific. Preserve point-in-time adjustments/minimumtick handling.
3. Preserve simulator trend50/stops5%/shorting semantics via bounded vectorbt proposals; signal timestamps become decisions atbarclose. Legacy `options.execution.extract_trades` marks openpositions closedatlastbar; **V7 must retain explicit censoring instead**. Develop full minute quote/expiry/roll replay,actual1–9DTE everypurchase,max60rollsexistingsemantics,noaggregatefills,completecounterfactualpaths and sharedledger.
4. Run all representative real/synthetic pilots, full-data no-swap verification and full-universe demand forecast against250GB. Only then finalizeimmutable source/runtime/data/feature/labelpolicy gates and fullbuild/training.

## V6 and Git

No new V6 recovery has been verified during this V7 work. Priorhandoff/incident records providerSep14NoSuchKey and retrytimer. Read saved status beforeclaimingrecovery. Installedhome runtime `/home/healy/Coding/HealysV6`, d6660af; separate numericalsource untouched. Do not sendtestnotifications. Dashboard/evidencejournal deployment still outstanding fromearlierwork.

Preserve many unrelated dirty V6 files and docs. Commit only scoped prerequisites/V7 changes. Generateddata/validationoutputs ignored and shouldstay outofgit. Source-only deployment usesgit, notscp. UpdateTODO scoped hunks, not unrelated preexistingchanges. Continue pushingcheckpointcommits and archive/rewrite thishandoff atnextmilestone.
