# ETFE 0DTE normalization and expanded Alpaca acquisition

The user explicitly permits same-day options when signals qualify and requests
normalization plus expanded acquisition. The selected immutable v4 setup uses
actual **0–5 calendar DTE**, default targets **0/1/5**, conditional weekly targets
**2/4**, and no target 7. Signal and dated expiry-cutoff guards remain required.
[Successor contract](../specs/ETFE_0DTE_NORMALIZATION_20261004.md),
[current machine scope](../specs/ETFE_SCOPE_0DTE_20261004.json).

## Completed acquisition and normalization

The new acquisition adds 96 stock-month partitions, 48 option discovery
partitions, twelve option bar/trade partitions and a 691-session Alpaca stock
calendar. **254 new live GETs all returned HTTP 200**. An initial sandbox-only
calendar failure is preserved separately. Stock capture resumed after its
128-request ceiling; the second invocation completed the remaining pages.

Combined with the earlier fresh bootstrap, all **186 data partitions** were
normalized to typed Parquet, preserving **1,677,986 rows**:

| Kind | Rows | Collection scope |
| --- | ---: | --- |
| Stock 1m bars | 1,589,090 | SPY/QQQ/VOO, continuous requested January 1, 2024–October 2, 2026 window, including outside regular hours |
| Option 1m bars | 5,399 | Four transport dates across all three ETFs |
| Option trades | 75,799 | Opening 30-minute windows for the sampled contracts |
| Fresh discovery records | 7,698 | Explicit selected expiries, both current statuses; discovery-only |

The new option strata cover November 29, 2024 (early close) and April 4, 2025
(busy market). Thirty-six target/right selections reduce to twenty unique
contracts; actual sampled DTE is 0 or 5. Target 1 sometimes selects the nearest
available same-day expiry under the declared distance rule. No selection exceeds
five days; there are no missing returned-contract strata in this sample. These
transport selections are not production point-in-time eligibility or a complete
option-chain/context census. Earlier transport dates were January 18, 2024 and
October 2, 2026. No old project data or metadata was imported.

## Quality and stock-session coverage

Normalized prices, volumes, counts and identities passed the implemented row
checks: no numerical/schema/duplicate-bar/condition flags in these selected
captures. This does not establish original publication timing or economic
contract terms. The complete raw occurrence sequence reconciles with Parquet
for every partition, including no-ID trades. Native timestamp strings, UTC
int64 nanoseconds, raw JSON and page/row/body-hash lineage are retained.

The newly fetched Alpaca calendar supplies 268,410 expected regular-session
minutes per ETF, with its holidays and early closes:

| ETF | Observed regular minutes | Missing minutes |
| --- | ---: | ---: |
| SPY | 268,410 | 0 |
| QQQ | 268,410 | 0 |
| VOO | 268,398 | 12 |

VOO's gaps occur on ten dates: May 22/24, September 13, October 3/8/14/22/23/30
in 2024 and August 7, 2025. October 14 has three missing minutes; the others have
one each. Exact UTC-nanosecond intervals are retained in the machine receipt
and normalized partition reports. Classify them as unresolved provider gap
versus no-trading, with **no synthetic fill or zero bar**. Raw request completion
is not a claim of complete observations. Stock-session classification on option
rows does not assert option-class expiry hours.

## Recovery, resources and checks

Normalization writes at most 5,000 rows per batch. It was deliberately stopped
after one real partition, then resumed; both the prior Parquet and partition
receipt hashes stayed unchanged. Unit tests also cover duplicate occurrences,
conflicting bars, invalid numerics, early-close grids, source/output corruption,
calendar tampering, DTE boundaries and qualifying-signal/expiry-cutoff behavior.
**87 focused tests passed.**

Two independent reconciliation reports validate all 1,677,986 raw-versus-Parquet
row occurrences in order and check row counts, hashes and quality counts.
Normalized roots occupy about **164.4 MiB** including reports/source snapshots;
maximum measured normalization process peak RSS was **208.2 MiB**. Main
normalization took about 39.9 seconds including the deliberately interrupted
first partition; the new option strata took about 1.6 seconds. These are
normalization measurements, not feature/ledger/model resource forecasts.

## Limits and next work

ETFE-1.normalize is implemented and complete for these selected captures;
bounded expansion is complete. The stock requests now span the chosen collection
window, with VOO gaps explicit. The earliest scoped options-history floor,
full option/context demand and coverage, dated contract/session admission,
causal features, integrated execution/resource pilot and research freezes remain.
January stock padding is not a newly verified options floor or extra model warmup.

0DTE is an entry candidate only when the signal qualifies and the dated expiry
clock permits entry strictly before close minus 15 minutes. Unknown expiry close
withholds the entry. Same-day IV timing uses positive remaining seconds to a
verified expiry close; no zero/one-day substitute. The helpers are tested
components, not a complete execution engine or live trading deployment.

[Machine receipt](2026-10-04-etfe-normalization-expansion.json) binds current
setup, raw/normalized manifests, reconciliation reports and source hashes.
Its evidence ZIP is a portable **index and report bundle**; the larger raw and
Parquet payloads remain in the local ETFE roots. No model evaluation or training
was performed, and readiness remains false.
