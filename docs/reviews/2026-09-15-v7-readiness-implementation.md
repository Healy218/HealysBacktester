# V7 preparation: implementation and integrated pilots

The user authorized all four readiness workstreams on September 15. Work is
in progress. This checkpoint does **not** authorize or establish full-universe
freeze, build or training readiness. External Pine comparison remains deferred.

## September 15, 22:40 UTC — current admission checkpoint

**All four workstreams have implemented, tested components. The requested
full-history preparation is not complete; full freeze/build/training stays blocked.**

### Data and identity

- Base: 8,284/8,284 captures. Hardened audit: 4,142 jobs, including 1,430 option days.
- Supplement: 167 roots, 2,004 captures, 1,002 raw/adjusted pairs.
- Actions: 7,113 Massive splits, 258,084 dividends; 242,932 Alpaca action records
  across all supported types, including name changes, mergers and spin-offs.
- The full adjustment diagnostic checked 3,714 pairs, 356,664,659 rows and
  804,596 stock-dates against explicit half-cent adjusted rounding tolerance.
  Only GS/NOW/USO on September 14 were incompatible. Fresh 2026 captures
  (`stock-repair-20260915`) pass timestamp and factor checks: 339,503 rows,
  525 dates, no remaining incompatibility in those replacements. Originals stay preserved.
- This establishes rounding compatibility, **not** a causal adjusted-feature
  vintage. Future actions and fixed tick size still require an explicit policy.
- Seven missing identity dates are resolved by reviewed trading-effective
  boundaries; see [identity evidence](2026-09-15-v7-identity-boundaries.md).
  Universe `v7-identity-universe-20260915r3`: 598 names, 596 identities,
  16,577 membership rows, `identity_boundaries_verified=true` for the checked
  transition set. Exact comparison with r2 leaves memberships/ranks/scores unchanged.
- A receipt-verified monthly-membership intersection examined 341,996 eligible
  stock sessions and found 215 zero-observation ticker/session combinations.
  Reproducible output: `v7-membership-session-coverage-20260915`, with
  `missing-sessions.csv` listing the 148 cases remaining after alias reconciliation.
  This is not a complete listing, intramonth-event or warmup admission audit.
- 67 of these now have same-FIGI, exact-day successor stock observations:
  FI→FISV (13), GOLD→B (15), SATS→ECHO (5), SQ→XYZ (9), DWAC→DJT (3),
  FB→META (15), GPS→GAP (7). Reproducible session routing evidence:
  `v7-gap-alias-resolution-20260915`. It never creates global aliases.
  GAP required one new 2024 raw/adjusted pair: 37,902 rows, timestamp parity,
  zero factor incompatibilities. This source was absent from the 598-name
  planning superset and must be added to any final identity-bound demand plan.
- Thirty isolated stock days were recaptured. All still lack regular-session
  bars. Twenty-six are March 8, 2022; the old BAC backup has the same gap,
  single-symbol bars do not repair it, and its SIP trade query returns only
  three opening-second records without pagination. Massive rejected that stock
  date under the current entitlement. See the [unsent support draft](2026-09-15-alpaca-stock-gap-support-draft.md).
- Three separate cases have primary-source trading-halt explanations:
  [BIIB June 9, 2023](https://investors.biogen.com/node/26871),
  [NVAX June 7, 2022](https://ir.novavax.com/press-releases/Novavax-Statement-on-Stock-Trading-Halt-FDA-Advisory-Committee-to-Review-Novavax-COVID-19-Vaccine?asPDF=1),
  [CLSK November 8, 2024](https://www.sec.gov/Archives/edgar/data/827876/000095017024127680/clsk-20241115.htm).
  VERU November 9, 2022 remains unverified as a full-session halt. The other
  118 candidate/session cases mostly surround lifecycle events and remain
  open for dated trading-status, identity and held-option disposition checks.

### Bounded storage and quote demand

`nn_meta/v7/factorized.py` stores repeated chart, parameter/strategy and tick
vectors separately, with int32 references and at most 65,536 rows per shard.
Explicit fold indices feed a bounded LightGBM Sequence. Tests establish exact
float32 reconstruction and selected-fold prediction equivalence to dense inputs.
The real 72-row pilot uses 39,664 numerical bytes versus 63,936 dense bytes;
this small result is not a full-campaign disk estimate. LightGBM's own binned
training dataset still needs a full-scale memory pilot.

The through-cutoff chain now has **22,142,875 contracts, 8,704 roots, 1,430 days**
(`v7-chain-through-cutoff-20260915`), completed in 106.67s, 5 GiB peak, no swap.
The batched selector matches all 19,500 saved SPY selections, including tested
expiry/strike tie rules. Full-history SPY selection is now a seconds-scale job.

`v7-full-quote-demand-20260915` finished all **598 names**, covering 227,849,091
observed stock minutes, 1,946,555 distinct per-root contracts, **11,327,841
contract-days / 76,222,710.75 quote-hours**. Largest worker RSS: 711,280 KiB;
service exit status 0. This is an intentionally broad inventory over all
candidate-name histories, not PIT-filtered; +15-minute closes are provisional.
No quotes were downloaded by this planner. It excludes unresolved stock gaps
and the newly added GAP source, so it is not the final demand proof.

Actual proposal/roll/feature interval unions and representative compressed
quote/trade densities must establish feasibility under the 250 GB cap before
full capture. Do not extrapolate the SPY week's density across all roots or
claim that this broad planning envelope itself fits the budget.

### Open gates

1. Repair genuine stock gaps; finish all identity-bound histories, sectors,
   lifecycle/holding paths and causal adjusted prices.
2. Resolve dated option-class hours and weekly eligibility. The latest user
   choice supersedes unresolved-only: funded physical exercise and stock
   delivery with observed stock liquidation. The new policy declaration is
   `V7_PHYSICAL_EXPIRY_20260915.md`; implementation and validation remain open.
   Existing replay/portfolio safeguards passed 17 focused tests, but those tests
   do not validate physical exercise. The fixed SPY call remains incomplete.
3. Complete actual required quote/trade/metadata demand, storage feasibility,
   full capture and full-history factorized assembly/resource pilots.
4. Bind those completed inputs to evaluation/source/runtime declarations and
   pass the full-universe executable gate before launching the campaign.

Regression evidence: **1,715 tests plus 18 subtests**, 83.56s, passed after
the gap capture/reconciliation scripts. The subsequent membership inventory
was exercised against all 341,996 eligible sessions. A clean archive of22fa5e8 also passed all**92 V7 tests** in17.10s.
Clean source validation remains separate from reproduction of dirty-runtime pilots.

## Later September 15 checkpoint — supersedes open implementation notes below

The complete row adapter now produces **222 columns**: the original 164 groups,
four timeframe indicators, 48 numeric parameter fields and six setup identities.
MA rows use the actual variant's windows. Daily IV uses contemporaneous raw spot;
returns use the separately declared adjusted history. Daily values become
available at the next captured regular open. The fixed BS rate/dividend inputs
remain explicit baseline proxies. Missing daily captures cannot be hidden by IV
forward fills. A real SPY daily artifact covers 300 sessions including 2021 warmup:
`nn_meta/validation/v7-daily-spy-20260915`.

`nn_meta/validation/v7-pipeline-pilot-20260915` ran all **11,268 variants**, preserving
**101,993 proposals** and explicit terminal censoring. The deterministic first
chronological proposal per family/timeframe produced 72 full feature rows;
70 sample labels completed observed exits and two remain censored at pilot end.
Families without proposals remain in the tested catalog. No outcome filtering
selects the sample. The four-worker service finished in 247.6 seconds with a
4.3 GiB memory peak and swap disabled. One-minute worker peak was 2,302,120 KiB.
Expanded source/runtime/input manifests and before/after mutation guards are
stored alongside results. This is plumbing evidence, not performance evidence.

The full disk-partitioned chain rerun also passed its resource pilot: 22,113,664
contracts in 99.32 seconds, 3.6 GiB peak, swap disabled. External-sort comparison
proved exact equality with the first catalog, canonical digest
`af3cf5b1c1a4b0618eaf9c332c67eebd2e181d3d4cc08681b92d05bfb50f9944`.
Evidence: `v7-chain-bounded-20260915` and `v7-chain-comparison-20260915`.

Dated standard-contract metadata is now enforced before quote features/fills.
All four tick windows pass real capture checks. The fixed real put replay
completed entry, expiry roll and final exit with observed marks; the matching
call remains unresolved because no eligible expiry bid was available. Missing
captures and complete-but-unfillable markets are separate statuses. No exercise
or abandonment return has been invented. The user's expiry-policy question is
pending; unresolved remains the default. These pilots still use the explicitly
provisional SPY session-close rule and do not establish full historical hours.

Shared allocation is implemented and tested: five slots, 10% equity, one symbol
across timeframes, causal score ordering, cash reservations until actual fills,
roll proceeds reinvested, and no new allocations without fresh held-position
marks. All preselected paths, including censored outcomes, enter the real shared
pilot (`v7-portfolio-pilot-20260915`). Captures and valuations are complete; one
position remains open at the pilot boundary, correctly leaving evaluation
incomplete. Unit tests cover simultaneous symbols, unavailable equity, pending
fills, and refusal to filter entries using future completion.

Historical supplementation adds 167 stock roots / 2,004 raw-adjusted year tasks
under the existing quota. Completion and coverage audits remain separate gates.
The seven unresolved identity dates, listing/alias continuity and price-vintage
checks remain open. Corporate-action capture now uses Massive's current
[splits](https://massive.com/docs/rest/stocks/corporate-actions/splits) and
[dividends](https://massive.com/docs/rest/stocks/corporate-actions/dividends)
endpoints; current cumulative adjustment factors are not treated as historical
point-in-time features.

Storage planning must avoid expanding repeated base features into a single wide
table. In this SPY week alone, 101,993 proposals share 2,509 timeframe/decision/side
feature windows and 37,711 decision/exit/side paths before DTE targets. Five
targets with 222 float32 columns would use 452,848,920 bytes before identifiers
or labels. This is a measured pilot count, not a full-universe size forecast.
Full-universe acquisition demand and bounded training assembly still need gates.

The later completed acquisition/audit milestone includes all 2,004 supplemental
tasks and 1,002 stock pairs (81,553,702 raw minute rows, matching timestamps).
September 14 option day/minute files are now captured. The hardened base audit
completed 4,142 jobs, including all 1,430 option days. Corporate capture completed
7,113 splits and 258,084 dividends after paced retries. These replace the earlier
pending acquisition statuses below. Latest regression: **1,707 tests +18 subtests**
in 82.42s; clean committed checkout: **84 V7 tests** in 17.13s.

## 1. Historical data and security identity

The first complete base audit inspected 2,712 raw/adjusted stock symbol-year
pairs and 1,429 option daily files. All 2,712 stock timelines match across price
bases, covering 275,110,957 raw minute observations. Of these pairs, 135 are
empty; 159 nonempty pairs have some sessions without observations. Those
counts do not establish why observations are absent. The audit rejects
duplicates, unordered/subminute timestamps, invalid OHLCV and changed receipts.
The subsequent receipt-path hardening also rejects a receipt redirected to a
different or nonexistent task. Original successful artifacts are preserved.

Evidence: `nn_meta/validation/v7-full-audit-20260915/`, reproducible with
`scripts/audit_v7_data.py`. Both September 14 option aggregate files remain
outside this completed audit pending provider availability and verification.

Captured reference evidence comprises 69 complete monthly stock security
masters, historical overviews and ticker events. The provisional identity-based
universe has **598 ticker names / 596 securities**, compared with the current
449-name reference. This is a candidate inventory, not an admitted universe.

High-confidence identity defects:

- `BITF` is Bitfarms; captured `DRAM` is Roundhill Memory ETF, listed April 1,
  2026. The legacy static `BITF → DRAM` mapping cannot be used for V7 continuity.
- `FIG` identifies Simplify Macro Strategy ETF in earlier captures and Figma
  in the current capture. Combining their price or liquidity history is invalid.
- 36 candidate ticker roots have changed FIGIs. These include genuine ticker
  reuse and corporate reorganizations; a changed FIGI alone does not distinguish
  those causes. The first targeted pass captured 791 daily observations over
  38 transition months. Broader capture requests cover 8,965 observations over
  430 transitions across the monthly masters, including historical competitors.

`nn_meta/v7/universe.py` now keys liquidity history by security identity and
uses exact-day captures in transition months. Uncaptured transition days block
identity admission. Supplemental stock acquisition, full listing/gap attribution,
corporate-action vintage validation and all feature dependencies remain open.
Monthly snapshots alone cannot prove every possible intra-month ticker event. The complete daily capture now totals 12,692 retained responses. The replacement universe `v7-identity-universe-20260915r2` retains 598 names / 596 securities / 16,577 membership rows. It resolves 424 transition months; three transition months still have observed option rows on seven dates with missing provider FIGIs (AESI, NUSI and BEPC). These are explicit unresolved inputs, not inferred identities. In total 90 successful daily responses lack FIGIs, but most have no option rows requiring a mapping.

Lists and evidence:

- Current reference: `docs/specs/v7-tickers-20260915.txt`.
- Provisional historical list: `nn_meta/validation/v7-identity-universe-20260915/symbols.txt`.
- Captures: `nn_meta/data_v7/reference-20260915/` and
  `nn_meta/data_v7/security-master-20260915/`.
- Daily requests: `nn_meta/validation/v7-all-identity-boundaries-20260915/`.

The earlier static-alias reconstruction in `v7-pit-20260915` is superseded as
an eligibility method; its 622 candidates include invalid/test roots. Neither
that artifact nor the 598-name draft should launch a campaign.

## 2. Strategy and timeframe adapters

Implemented all 20 strategy families and all registered parameter variants for
1/5/15/30-minute charts, retaining four signal channels and stable variant IDs.
MA shares window calculations; other legacy variants use their existing exact
kernels in bounded output batches. No global winner or 2,000-event cap applies.

All 13 source groups project 96 features with completed-bar availability.
Minute-derived opening range/VWAP, actual session boundaries and declared local
HTF assumptions are separate V7 context. The V7 Setup Scanner is isolated from
the activated V6 runtime. Local HTF assumptions remain 240m/720m/2D and are not
external TradingView parity evidence.

Real SPY March 7–11, 2022 pilot, retaining 2021 warmup:

| Chart | Variants | Warmup + signal bars | Wall seconds | Worker peak KiB |
|---|---:|---:|---:|---:|
| 1m | 2,817 | 116,815 | 189.34 | 2,239,272 |
| 5m | 2,817 | 23,364 | 50.89 | 708,896 |
| 15m | 2,817 | 7,788 | 29.43 | 586,724 |
| 30m | 2,817 | 3,894 | 21.90 | 558,900 |

All **11,268 variants** ran. Evidence:
`nn_meta/validation/v7-signals-pilot-20260915r2/` and
`scripts/pilot_v7_signals.py`. The first attempt failed a Polars timezone-type
comparison; the replacement compares UTC nanoseconds. The successful pilot
has 96 TradingView and 15 technical columns. It does **not** yet assemble the
full model-facing surface/context/tick/parameter/sector feature schema or labels.
Its saved base technical table uses 10/30 windows; MA rows still need their own
registered fast/slow feature values during row assembly.

The original all-market chain catalog contains 22,113,664 contracts / 8,702 roots.
Its first global grouping used 5 GiB RAM and 16.2 GiB swap, so it fails the
resource gate despite producing a completed file. `scripts/build_v7_chain.py`
now partitions grouping on disk; the small exactness test passes. Full-data
no-swap rerun and catalog equivalence remain required.

## 3. Observed quotes, execution and accounting

Declared policy: one-second latency, 60-second entry deadline, 30-second mark
age, positive uncrossed bid/ask and reported size, 100-share multiplier,
0.10% fee plus 0.05% slippage per side in addition to the observed spread.
Five shared slots and 10% fractional-paper allocations preserve the research
comparison convention. This does not establish broker fills or queue/size access.

The ledger buys at observed ask, sells/marks at causal bid, keeps unresolved
exits open, and checks actual **fill-date** 1–9 DTE on every purchase. Invalid
latest quotes cannot be bypassed by searching back to older valid marks.
`QuoteArchive` verifies original shard hashes and complete window continuity;
absent shards are not classified as observed-empty markets.

The outcome-independent SPY week plan covers every minute, both rights and
all five target choices: 19,500 selectors, 148 contracts and 516 contract-days.
It includes retained contracts through expiry or pilot end. Weekly eligibility
and dated option-class session rules remain separately unverified.

A fixed first-minute sample (both rights, target 1/5, March 7 only) captured
216 shards: **511,826 quotes / 6,731 trades / 9,554,654 bytes**. A predetermined
one-hour replay produced two observed fills, 60/60 causal minute marks and
reconciled cash/costs. This is execution plumbing evidence, not a strategy return
or a complete roll/portfolio evaluation. See
`nn_meta/validation/v7-quote-volume-pilot-20260915/replay.json`.

The complete SPY week capture finished: **27,864 shards / 72,894,383 quote and trade records / 1.321 GB**. All 516 dated contract-day metadata responses report American exercise, 100 shares and no additional deliverables. These still require binding into the execution loader. Full-universe quote demand,
contract deliverables, expiry/roll replay, overnight marks, feature windows and
250 GB feasibility still require measurement. Shared acquisition accounting
remains under `nn_meta/data_v7/quota.json`; do not reinitialize it while captures run.

MASSIVE's [contract overview](https://massive.com/docs/rest/options/contracts/contract-overview)
supports a dated query and reports deliverables. Observed aggregate appearances
alone do not establish standard 100-share contracts.

## 4. Evaluation and validation

`docs/specs/V7_EVALUATION_20260915.json` was declared before V7 training. It fixes
expanding validation windows 2024H2, 2025H1 and 2025H2, final evaluation January
1–September 14, 2026, ten captured-session embargo, train-only fitting, and
purging by full completed exit/roll horizons. Earlier dates remain warmup only;
known evaluation periods are explicitly revalidation, not untouched holdout.
Policy hash: `f03272ee3545b08c2dbb4deb2d92da3ad32b3e323923e9ff630ef6f94a119ae3`.
Do not rewrite this declaration; amend with a new version if necessary.

The first full-suite checkpoint passed **1,671 tests + 18 subtests** in 81.24s.
Log: `/tmp/healys-v7-readiness-milestone-tests.log`. Subsequent focused tests cover
quote shard boundaries/tampering, receipt paths, ticker reuse and disk-partitioned
chain exactness. The updated full suite passed **1,682 tests + 18 subtests** in 80.25s, log `/tmp/healys-v7-readiness-final-r2-tests.log`. Its preceding run exposed eager Polars initialization in the chain module; initialization now happens under the explicit thread guard. Full-pipeline admission remains open.

## Next work, in dependency order

1. Finish exact identity evidence, rebuild membership, restore newly eligible
   historical stock roots, classify empty/gapped sessions and bind price vintages.
2. Finish full feature/row assembly, parameter-specific technicals, historical
   surface/context and quote/trade windows, with source/runtime guards.
3. Validate dated contracts/session rules and complete quote-based strategy,
   expiry/roll and shared-portfolio pilots; measure full-scope acquisition demand.
4. Pass no-swap and complete-universe readiness gates, bind all manifests and
   evaluation settings, then proceed to the authorized build/training sequence.

No full campaign or V6 numerical deployment is launched by this checkpoint.
