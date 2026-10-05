# ETFE phase-B option-trade window capture

Completed all **225 missing trade intervals** from the audited January component
pilot. Exact start/end grouping reduced them to **103 physical queries** across
68 contracts. Alpaca returned **77,057 trades in 105 successful HTTP requests**;
all query page chains terminated. No interval was widened, and no old project
data or metadata was used. [Study contract](../specs/ETFE_TRADE_CAPTURE_20261004.md).

## Capture and normalization evidence

The first invocation stopped after one successful request. Resume preserved its
three committed page/receipt/body files and completed the remaining queries.
Two invocations consumed 103.94 seconds of active capture time; all requests
returned HTTP 200. The largest recorded capture-process peak RSS was 0.78 GiB.
Raw storage is 5,803,732 bytes; normalized data plus audit artifacts is 6,751,973
bytes. The 512-request, 8-invocation, 30-minute active-time and 512-MiB raw-root
ceilings were respected. The preflight scenarios and original limits remain
bound in the capture plan; approval/idle time is excluded from active time.

Typed normalization produced **103 partitions / 77,057 occurrences**. Every
partition's ordered raw-row sequence independently reconciles with its Parquet;
all native timestamp strings equal the typed integer nanoseconds. No implemented
quality flag fired, and no identical raw trade content was removed. The separate
window audit verifies every returned row against its exact half-open request,
all 225 symbol/interval edges, all original logical membership file hashes,
and the previously captured bars. The initial auditor invocation found a
relative-path handling error before publishing output; the corrected auditor
passed and its source hash is recorded.

## Demanded-minute observations

| Observed state | Contract-minutes |
| --- | ---: |
| Trades and a bar | 2,200 |
| Trades without a bar | 3 |
| Bar without trades | 0 |
| Neither observed | 2,423 |
| **Total requested** | **4,626** |

There are **54 entirely empty intervals**. Completed transport and absence of
records do not establish valid no-trade history. The minute census retains
explicit absence reasons and sets model-feature/no-trade admission false.

The three trade-without-bar minutes on January 19, 2024 are:

- `SPY240124C00478000`, 16:48 UTC: one observed trade.
- `SPY240124C00479000`, 17:07 UTC: five observed trades.
- `SPY240124P00479000`, 16:19 UTC: one observed trade.

Their seven raw occurrences and lineage are retained in OBSERVATION_EXCEPTIONS.
Bar absence remains unresolved; none is replaced with an inferred execution
price. All **77,057 records lack native trade IDs**. There are **166 additional
equal-time occurrences across 130 minutes**. Occurrence IDs preserve every
record, but they are not provider trade IDs or a verified ordering of equal-time
prints. Signed-trade features must handle this unresolved order explicitly.
No minute has conflicting/multiple source bars in the selected input inventory.

## Artifacts, checks and remaining work

Raw: `nn_meta/data_cache_etfe/alpaca-fresh-20261004-trade-windows-r0/`.
Normalized: `nn_meta/data_cache_etfe/normalized-20261004-trade-windows-r0/`.
Evidence: `nn_meta/validation/etfe-trade-windows-20261004-r0/`.
Capture plan SHA256:
`e4eb9897d58af3ea9ea9596d0e7bf913b05b1fffc8e3cde26582b38d9ee40b4b`.
Normalization plan SHA256:
`53ec002bc63e2a9ec291e98e859f23fe53a9272026705b593364fa8542012e47`.
The 4,626-row DEMANDED_MINUTES Parquet SHA256 is
`a72a2d28b546d74aab10e8bb0f7c98704a5a12a49d75a794236ff7e3db0e4560`.

**116 focused tests passed**, including exact interval conversion, batching,
non-overlap and cumulative request/time/invocation budget exhaustion. Raw resume,
normalization reconciliation, timestamp equality and real minute/edge audits
passed separately. Two installed-protobuf deprecation warnings remain.
The [machine receipt](2026-10-04-etfe-trade-windows.json) and
[evidence ZIP](2026-10-04-etfe-trade-windows-evidence.zip) retain the measurements,
source snapshots and metadata. The ZIP contains 349 members and hashes for
209 local raw-body/Parquet payloads; payloads remain in the ETFE roots.
ZIP SHA256: `ce3f224b72c1c96e5475b4e7874180bfa5967cd4fc7fe0b18e229d333945df56`.

Selected normalized ETFE inputs now total **1,249 partitions / 1,955,680 rows**,
including 152,856 option trades. The original pilot GLOBAL_DEMAND stays immutable;
DEMAND_AUDIT records that its 225 missing trade intervals are now captured.
This closes **ETFE-1.trade-window-capture**, with zero remaining transport
intervals for that bounded trade inventory. It does not close full-history
coverage, historical eligibility, option-hour/condition/publication provenance,
full phase-B/C demand, the final feature schema or integrated ETFE-4.pilot.
Next is the trade/bar feature consumer with explicit condition, availability,
missingness and equal-time-order rules. No execution, training or deployment.
