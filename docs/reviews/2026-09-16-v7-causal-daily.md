# September 16 V7 causal daily calculations and rebuilt parent artifacts

The midpoint amendment invalidated parent manifest hashes in the prior daily
stock/surface chain. Both full datasets were rebuilt into new immutable paths;
every old observation and missing value was independently reconciled. No old
option execution labels, marks or portfolios were relabeled.

Implemented `nn_meta/v7/causal_daily.py` and verified real dividend-boundary
returns. Full-universe action/identity admission and market/sector integration
remain unfinished. **V7 is not ready to train.** No V6 runtime changes this turn.

## New full-scope artifacts

| Artifact under `nn_meta/validation/` | Scope | Complete receipt SHA256 |
|---|---|---|
| `v7-stock-daily-20260916-midpoint/summary` | 2,966 shards; 669,749 raw calendar rows; 339,640 eligible sessions | `14f2ba3f97c5f338ab9553ceb81f35938ff49820c3495b8bcdb79e090528a85b` |
| `v7-surfaces-20260916-midpoint/summary` | 1,129 days; 339,640 eligible rows; 591 identities | `cb0651b00cf1c448aacba5903c4ecc641061d3ee577b5b97d051ec24573f17be` |
| `v7-daily-rebuild-verification-20260916` | All-shard/all-row comparison and current parent checks | `9a1b86dfe4f738d08458d2048631a381e71f3ba832249780aa01600e83a17a93` |

All 2,966 raw-stock shard receipts are byte-identical to the prior build. All
1,129 surface tables and both 339,640-row eligible tables have identical values
(surface receipt hashes necessarily differ). Current parent input/source hashes
passed. Verification source is preserved as `verification.source.txt` beside its
report and receipt. Old outputs remain preserved.

Missingness remains explicit: 59 stock sessions, 30,447 near-IV values, 44,678
far-IV values and 177 put/call ratios. The surface still uses daily option trade
aggregates for a declared IV proxy; it is not an executable quote or a modeled
midpoint fill. Four outer workers/one inner thread and the 100 GiB reserve were
used. No new provider acquisition occurred. This is not a full resource gate.

Commands completed with exit 0:

```bash
./venv/bin/python scripts/build_v7_stock_daily.py \
  --output nn_meta/validation/v7-stock-daily-20260916-midpoint --workers 4
./venv/bin/python scripts/build_v7_surfaces.py \
  --stock-daily nn_meta/validation/v7-stock-daily-20260916-midpoint \
  --source nn_meta/data_v7/start-20220315 \
  --audit nn_meta/validation/v7-full-audit-20260915r2 \
  --availability-calendar nn_meta/data_v7/exchange-calendar-20260916 \
  --output nn_meta/validation/v7-surfaces-20260916-midpoint --workers 4
```

Logs: `/tmp/v7-stock-daily-midpoint.log`, `/tmp/v7-surfaces-midpoint.log`.

## Causal daily contract

`returns` requires complete calendar rows, an explicit security, reviewed
continuity spans and an upstream action-evidence identity. For adjacent observed
sessions in the same span, log return is `log(close_t)-log(close_t-1)-log(factor_t)`.
Only reviewed actions effective at the captured session open contribute; later
actions cannot rewrite prior rows. These are chart returns, not a dividend cash
ledger. No-event completeness and identity review remain the caller's admission
obligation; a string ID alone is not evidence of that review.

Missing stock sessions and identity discontinuities break returns and rolling
warmup. Unknown identities stay unknown. Nullable string spans are normalized
so missing days produce explicit statuses instead of a pandas boolean error.
Five/21-session annualized volatility uses complete adjacent log-return windows.
The context projection supplies the ten declared daily columns, explicit market
returns/IV, 60-session beta, within-span five-session IV change, put/call cap 5
and next captured regular-open availability. It never forward-fills surfaces.
Warmup reports preserve missing counts and first source/availability dates.

The old `daily.daily_context` remains historical component code with a different
declared adjusted/filled policy. The full builder must consume `causal_daily`,
reviewed identities/actions, the rebuilt stock/surface chain and dated sectors;
this commit does not admit old daily context for the new run.

## Tests and actual-data evidence

**1,851 tests +18 subtests passed**, 18 warnings, 97.13 seconds.
Log `/tmp/v7-causal-daily-final-tests.log`. Seventeen new cases cover split,
cash/combined factor boundaries, independent chart parity, future-data/action
invariance, missing sessions, identity breaks, nullable identities, surface
absence, availability, beta and invalid input rejection.

`scripts/validate_v7_causal_daily.py` independently replays the reviewed AAPL
March 15–May 10, 2022 interval from the rebuilt raw daily shard and original
action captures. It verifies retained source payloads and binds source/runtime
and input hashes. Result `v7-causal-daily-aapl-20260916r2`, receipt
`3aa6037bfb96cce9bf92b00314cc09cc37494ade8ed09c5e96f4d183b1141ccb`:

- 40 actual sessions, 39 returns compared with independently reconstructed
  as-of minute-chart closes; maximum absolute error `7.8236028766554e-16`.
- All 40 prefix comparisons passed; future dividend evidence left the earlier
  return prefix unchanged.
- First five-return volatility source March 22; first 21-return volatility
  source April 13. Initial price history starts March 15.
- Reviewed May 6 dividend: $0.23, prior raw close $156.81, chart factor
  0.9985332568076015. Original publication and provider reconciliation are in
  the earlier [AAPL evidence review](2026-09-16-v7-causal-feature-pilot.md).

The initial actual-data output `v7-causal-daily-aapl-20260916` is preserved under
its old source binding. The r2 rerun includes the nullable-span fix and explicit
payload mutation guards. Log `/tmp/v7-causal-daily-aapl-r2.log`, exit 0. No source
changes followed the final validation/test runs.

## Remaining admission

Readiness `v7-readiness-20260916-causal-daily-final.json` still passes three input/
membership/coverage checks and lacks eight substantive stage artifacts. Next
work is full reviewed identity/action continuity, causal market/security panels
with dated sectors, actual quote demand/capture, funded lifecycle/expiry paths,
full assembly/trials and measured resource/coexistence gates. All requested dates,
variants, 222 columns and data-source constraints remain intact. No training ran.
