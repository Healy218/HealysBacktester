# V7 joined-range forecast and packed capture — September 26–27

The representative joined-range forecast and lossless packed capture/reader are
implemented and validated. V7-3 remains open; no bulk acquisition or training
was launched. Existing catalog, demand, daily, union and storage-migration
freezes were preserved. V7-1/V7-2 remain completed milestones.

## Full-population joined forecast

`plan_v7_joined_sample.py` rescanned the 591 sealed demand databases and
reconciled all 76,910,536 requests, 2,223,844 contract-days, 10,941,828 joined
quote/trade ranges and the exact prior union duration. Joining adds no seconds.
The outcome-blind seeded sample uses 60 strata: five years, four demand-size
quartiles and three joined-duration buckets (≤15 minutes, ≤60 minutes, longer).
Twelve paired windows per stratum yield 720 pairs / 1,440 captures over 376
securities. The sample frame is over joined ranges, not the earlier fixed cells.

All 1,440 downloads passed, with **1,168,551 records** and zero provider failures
in the network-enabled run. The restricted-network attempt is retained with
explicit failed attempt receipts. Sixty bounded packs took 86.21 seconds;
extrapolating that sample throughput to the entire range census is roughly
7.6 days without retries or rate changes, not a completion-time guarantee.
No sampled range exhausted the four-page bound. Dense-range split behavior
is tested: only an explicit incomplete-page-budget error triggers exact time
bisection, preserving the failed parent attempt and adding no gaps or seconds.
Other failures prevent publication and cannot be omitted from the forecast.

| Measured layout | Entry capture estimate | Standard error | Mean plus 3 SE |
|---|---:|---:|---:|
| Lossless JSON columns / zstd, packed v1 | 169.84 GB | 14.27 GB | 212.66 GB |
| Integer deltas / shuffled IEEE doubles / zstd, packed v2 | 139.17 GB | 10.52 GB | 170.74 GB |

V2 re-encoded the same captured sample without new downloads. Integer deltas
preserve arbitrary integer values and nanoseconds; doubles preserve their
actual IEEE representation, including negative zero. Mixed types, absent
fields, explicit nulls, nested values, order and duplicate prints are retained.
Every decoded stream has the same canonical raw bytes as v1. Both versions
remain separately sealed; the v1 producer and artifacts were not overwritten.
Measured v2 packs total 15,442,224 bytes, including 2,190,498 bytes of actual
SQLite/index/receipt overhead. The earlier experiment's modeled 128-byte
index allowance is not used.

The separate on-disk routing index measured 423,382 bytes. Linear scaling adds
**3.217 GB** at the sampled 24-capture pack size. Entry including routing is
therefore **142.389 GB**, or **173.954 GB** at mean plus three SE. These are
planning estimates, not hard upper bounds or statistical tail guarantees.
The sample does not cover held-position execution or training storage.

## Packed capture implementation and consumer proof

- `nn_meta/v7/packed_quotes.py` and `packed_quotes_v2.py`: immutable SQLite
  packs, lossless encoding, exact provider manifests and per-payload hashes.
  Packs are bounded to 256 captures / 512 MiB, with a 256 MiB decoded-payload
  limit. Publication is atomic; interrupted directories remain unsealed.
- `nn_meta/v7/packed_quote_index.py`: SQLite interval routing with bounded pack
  cache. Gaps, overlap, drift and missing packs fail closed. It exposes the
  existing `window`, `first_fill` and `mark` interface without loading the
  full population's interval map into RAM.
- `scripts/capture_v7_packed_batch.py`: direct v2 download for an explicit
  bounded consumer request batch, with original request memberships, shared
  acquisition reservations, disk/project guards and immutable attempt evidence.
  This is not a full-population scheduler or a training-adapter admission.
- The original six adjacent-range cases passed all **126** original request
  reads after packing. The broader sampled indexed archive passed **12,760**
  original frozen-demand request reads across **376** securities. Canonical
  raw records and causal window hashes matched exactly.
- Five additional real one-minute purchase windows, one in each year, were
  captured directly to v2. DIS, ABBV, NVDA, VKTX and FUTU produced valid observed
  midpoint paper fills and causal final-minute marks under the existing
  consumers. These are consumer checks, not complete trade paths or returns.

The current production assembly adapter still needs explicit packed-index
binding/integration during 7-5. The library's consumer API and the selected
real checks do not establish full assembly or physical/shared-capital execution.

## Dated references and hours follow-through

`plan_v7_dated_references.py` derived the exact pre-entry consumer demand for
all 591 securities: **2,223,844 contract/date references** and **301,213
root/date session references**. Each security has sealed SQLite request lists.
Held paths can add dates; this is not a complete lifecycle reference census.

All **720** sampled contract/date queries completed. **715** passed the actual
`ContractReferences.standard` validator. Five returned immutable HTTP 404s:

| Contract | Consumer date |
|---|---|
| CMA230630C00041000 | 2023-06-22 |
| FANG220520P00130000 | 2022-05-18 |
| MSTR230630P00320000 | 2023-06-27 |
| RH230630P00290000 | 2023-06-22 |
| VFC230630C00019000 | 2023-06-28 |

Narrow same-date list queries, with exact underlying/expiry/right/strike and
both active/expired filters, returned zero exact matches for all five. No
alternate contract, date or assumed standard deliverable was admitted. The
provider documents `as_of` as the historical contract-date parameter:
[Massive contract overview](https://massive.com/docs/rest/options/contracts/contract-overview).
These are concrete missing metadata inputs despite retained tick observations.

Thirteen named Nasdaq pages were captured with source receipts for dated hours
work. Notices confirm changes that must not be backfilled across all history,
including [IYR, November 11, 2024](https://www.nasdaqtrader.com/MicroNews.aspx?id=2024-71a),
[SLV, February 18, 2025](https://www.nasdaqtrader.com/MicroNews.aspx?id=OTA+2025-10),
[IEF, May 27, 2025](https://www.nasdaqtrader.com/MicroNews.aspx?id=2025-22),
[SMH/SOXX/SOXL, August 25, 2025](https://www.nasdaqtrader.com/MicroNews.aspx?id=OTA+2025-36),
and [IBIT, November 10, 2025](https://www.nasdaqtrader.com/MicroNews.aspx?id=2025-52).
The [IVV notice](https://www.nasdaqtrader.com/MicroNews.aspx?id=OTA+2026-17) is
published April 20, 2026 but its body says April 21, 2025; that conflict is
unresolved, not silently corrected. The current hours page alone does not
prove a full 2022–2026 dated schedule. No complete hours input has been sealed.

## Capacity and readiness

The final snapshot measured 437.831 GB local apparent project bytes, 286.242 GB
free internally, and a preserved 35.107 GB historical archive on MRHA.
Reflink savings are not subtracted from logical project bytes. The acquisition
ledger had 180.983 GB remaining and no reservations at the snapshot.

The maximum sampled reference-directory size (782 bytes) times the exact
reference census gives a **1.739 GB planning allowance**. This is not a proved
upper bound. Entry + routing + that allowance total **175.693 GB** at the
three-SE sensitivity, leaving only **5.290 GB** of acquisition allowance for
additional paths and recovery. A full execution-path forecast is still missing.

- Local project plus that entry/reference stress estimate: **613.524 GB**.
- Including the preserved MRHA archive: **648.631 GB**.
- Both exclude additional held paths, full assembly/training outputs and
  in-flight/recovery allowances. The 20 GiB operating disk reserve, 250 GB
  acquisition cap and 640 GB project cap remain unchanged.

The user was asked whether the existing project cap includes MRHA's historical
archive. No answer or cap increase is inferred. Even a local-only interpretation
would not establish the missing full-path budget or training readiness.

The legacy `v7_readiness.py` check remains false. It also needs migration to the
completed 7-1/7-2 receipt model and current amendments: it currently reports an
active-input amendment mismatch and absent generic stage receipts, including
old `222_columns` terminology. That wiring failure does not revoke the separate
sealed 7-1/7-2 completion evidence. Do not rewrite frozen declarations to make
the legacy check green or present this packed-sample report as full readiness.

Next: resolve source-backed historical sessions and the five metadata gaps;
complete actual purchase/mark/exit/roll/delivery demand and its storage budget;
then run a budget-gated resumable packed campaign. After full 7-3 coverage,
finish integrated execution, assembly/folds, resource/recovery and the final
readiness receipt. Training remains unstarted.

## Evidence

Under `nn_meta/validation/`:

- `v7-joined-volume-sample-20260926` and sibling per-security checkpoints
- `v7-joined-packed-forecast-20260926`
- `v7-joined-packed-v2-forecast-20260926`
- `v7-packed-quality-20260926`, `v7-packed-index-proof-20260926`
- `v7-direct-packed-fills-20260927`, `v7-direct-packed-fill-consumer-20260927`
- `v7-dated-reference-demand-20260927` and sibling per-security checkpoints
- `v7-joined-capacity-review-20260927`
- `v7-readiness-after-packed-20260926.json`

Raw packs/references/source pages remain in their named `nn_meta/data_v7/`
outputs. Old and new evidence coexist; no prior freeze was relabeled.

Validation: final full suite **2,441 passed + 18 subtests, one skipped**, 20
warnings, 123.97 seconds. Ten focused pack/codec/routing/split tests pass. The
initial suite encountered the intended source-mutation guard while new files
were being authored; the final stable-source run passed. All nine sealed
new evidence roots and direct input/source hashes reverified. Final acquisition
ledger: 69,017,114,207 / 250,000,000,000 bytes, no reservations.
