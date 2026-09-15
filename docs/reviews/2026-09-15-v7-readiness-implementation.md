# V7 preparation: first implementation checkpoint

The user authorized all four readiness workstreams on September 15. Work is
in progress. This checkpoint does **not** authorize or establish full-universe
freeze, build or training readiness. External Pine comparison remains deferred.

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
