# V7 full-universe raw daily stock inputs

## Completed build

`nn_meta/v7/stock_daily.py` and `scripts/build_v7_stock_daily.py` aggregate
existing receipt-verified Alpaca minute captures into immutable symbol/year
regular-session daily facts. The complete run is stored at
`nn_meta/validation/v7-stock-daily-20260916`.

| Check | Result |
|---|---:|
| Completed symbol/year shards | 2,966 |
| Source stock tickers, including verified aliases | 594 |
| Raw calendar rows | 669,749 |
| Security identities in eligible join | 591 |
| Eligible membership sessions | 339,640 |
| Eligible sessions with observations | 339,581 |
| Explicit eligible zero sessions | 59 |
| Exact-date verified alias sessions | 67 |

The raw archive retains available scoped years for the source tickers. Raw dates
outside eligible membership have no inferred security identity and are not
admitted feature rows. The eligible table assigns identity only from the exact
date/ticker mapping already frozen in the coverage inventory; all 339,640 rows
match every original coverage field. No excluded issuer is present in that join.

All prices remain **raw Alpaca observations**. The last reported regular-session
minute is the daily close proxy, with its exact observation time retained. It is
not represented as an official closing-auction price. Availability is the
captured session close; downstream daily features still become available at the
next session open. Pre/post-market observations, March 8–14, pre-March-15 prices,
and dates after September 14, 2026 are not included in these outputs.

Empty sessions retain missing OHLCV and missing observation clocks. No quiet
minutes or absent sessions are filled. Early closes use actual captured session
bounds. First/last observation nanoseconds use nullable integer columns, avoiding
loss of precision when empty days appear beside observed ones.

## Verification and recovery

Build and exact completed resumption both exited successfully with four outer
workers and one inner thread. Each worker holds one symbol/year of minute data.
The rerun verified source payloads and completed output hashes, then reused all
2,966 shards. The final summary receipt stayed byte-identical:
`e59e2259259c95c524bc493a889663a5a897f156400e0d6a316de2f54d94e8ea`.

Independent full-table verification checked all eligible rows, every price and
clock, captured session alignment, zero-session missingness, identity exclusions,
and exact coverage equality. Results:
`nn_meta/validation/v7-stock-daily-verification-20260916.json`.
The exact one-off audit source is retained as `verification-source.txt` beside
the build, with its hash in that verification report. `build.log` and `resume.log`
retain the completed process output.

Four new focused regressions pass: regular/early session boundaries, cold-start
exclusion, empty captures, precise nullable clocks, exact alias joins/count
reconciliation, immutable reuse and source mutation rejection. Full suite:
**1,817 tests plus 18 subtests**, 18 warnings, 106.89 seconds.
Log: `/tmp/v7-stock-daily-20260916-tests.log`. No code changed after that suite.

Reproduction (completed output is verified and reused):

```bash
./venv/bin/python scripts/build_v7_stock_daily.py \
  --output nn_meta/validation/v7-stock-daily-20260916 --workers 4
```

Derived output occupied approximately 142 MiB when measured; no additional
provider data was downloaded. Acquisition quota remains 62,557,919,862 bytes,
with no outstanding reservations. The builder checks the 100 GiB disk reserve.

## What remains

This completes the full-scope **raw daily stock preparation**, not the full
`daily_context` readiness stage. Original corporate-action evidence, causal
return adjustment, all-security option surfaces, market/sector context, initial
feature warmup and first-eligible-feature observations still need integration.
The 59 zero sessions remain subject to lifecycle/execution routing.

The host had more than 23 GiB available RAM at both sampled points, but global
swap counters increased between a mid-build and late-resume observation.
`resource-observations.json` records the exact counters. They cannot isolate
attribution to this job versus other activity. **No no-swap or V6-coexistence
resource gate is claimed.** The independent full binned-dataset/resource pilot
remains necessary. V6 runtime and settings were not changed.
