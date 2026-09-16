# V7 full daily option-surface preparation

## Completed and independently verified

`nn_meta/v7/surfaces.py` vectorizes the declared daily European Black–Scholes
proxy across source tickers. `scripts/build_v7_surfaces.py` runs immutable day
shards with at most four workers and one inner thread, joining all eligible
identities only after calculating raw ticker-level facts.

Output: `nn_meta/validation/v7-surfaces-20260916r2`.

| Check | Result |
|---|---:|
| Completed option days | 1,129 |
| Raw ticker/date surface rows | 669,749 |
| Eligible identity/date rows | 339,640 |
| Eligible identities | 591 |
| Rows with admitted option observations | 339,517 |
| Explicit missing stock observations | 59 |
| Observed stock, no matching option observations | 49 |
| Observed stock/options, none meeting tenor/premium filter | 15 |
| Missing near IV | 30,447 |
| Missing far IV | 44,678 |
| Missing put/call ratio | 177 |

All counts are descriptive input coverage, not execution or performance results.
Missing IV may reflect missing near-ATM/tenor observations even when other
contracts were observed. No surface values are forward-filled. The stock-absence
flag takes priority; observed option volume can remain present on those dates,
but IV stays missing. The raw ticker archive confers no identity or eligibility
outside dated membership. Literal option roots are not deliverable/alias proof.

All raw Massive daily receipts and audited contract payloads are hash-verified.
The audit receipt must point to the exact active raw receipt. All raw stock
summary/shard parents, payloads and code are bound; the CLI checks the active
manifest and raw-source root. Output writes reject changed inputs/code and use
atomic completion. Existing completed stores are verified before reuse.

Proxy assumptions remain those of the declared baseline: 1–45 calendar DTE,
minimum premium $0.20, absolute log moneyness below 0.01, near tenor at most 20
days, fixed annual rate 0.0425 and dividend yield 0.012. Inversions exceeding the
5.0 volatility solver ceiling remain missing. These are engineered European
proxies, not observed IVs, American-option fair values or executable prices.

## Captured exchange-calendar extension

The first invocation stopped before any option-day writes because the old
calendar ended September 14. The completed stock index from that attempt is
preserved at `nn_meta/validation/v7-surfaces-20260916`; do not reuse it under the
changed source binding.

Captured Alpaca's exchange calendar for January 1, 2021–October 31, 2026:
`nn_meta/data_v7/exchange-calendar-20260916`, 1,464 sessions. Original API bytes,
normalized records, request/UTC capture metadata and the exact one-off capture
source are retained in the verified receipt. The captured records match every
session, open and close in the original calendar's shared coverage. The builder
requires that agreement and raw/normalized record equality; it never guesses the
session after the study endpoint or mutates the active stock calendar.

Each surface is available at the next captured regular opening. The final source
session, September 14, becomes available September 15, outside the study's entry
window; this adds no price observations or labels beyond scope. This exchange
calendar is **not** the unresolved settlement/physical-exercise calendar.
Shared acquisition ledger: 62,558,385,604 /250,000,000,000 bytes, no reservations.

## Verification

Independent audit reconciled every eligible row with its original raw stock
facts and day surface, every final receipt reference, every observation count,
and all exact next-session nanosecond clocks. It verified all 1,129 shards and
original active raw/audit lineage. Scalar/vectorized equality passed on 58
stock/day checks across 12 dates, including early closes, action dates and the
last study day. Report:
`nn_meta/validation/v7-surfaces-verification-20260916.json`.
Exact audit source is retained as `verification-source.txt` beside the build.

Build, audit and full completed resumption all exited 0. Summary receipt remained
byte-identical before/after resumption:
`c5ae589033a8262d0b914a3fd1e0553cff52232aa0e12193540db4c957d3da0e`.
Derived artifact bytes before copying diagnostic logs: 105,637,325 (about 101 MiB).

Seven new surface tests cover scalar equality, empty captures, absent raw spot,
duplicate/malformed observations, ambiguous roots, over-ceiling premiums,
immutable resumption, raw-source mutation, parent/lineage mismatch and calendar
overlap/raw-record equality. Full suite: **1,824 tests +18 subtests**, 18 warnings,
108.99 seconds, `/tmp/v7-surfaces-20260916r2-tests.log`. No code changed afterward.

Completed command:

```bash
./venv/bin/python scripts/build_v7_surfaces.py \
  --stock-daily nn_meta/validation/v7-stock-daily-20260916 \
  --source nn_meta/data_v7/start-20220315 \
  --audit nn_meta/validation/v7-full-audit-20260915r2 \
  --availability-calendar nn_meta/data_v7/exchange-calendar-20260916 \
  --output nn_meta/validation/v7-surfaces-20260916r2 --workers 4
```

## Still required

No full `daily_context` readiness claim. Causal daily returns require reviewed
original action evidence and dated identity continuity; market/sector alignment,
initial warmup/missingness reporting and complete feature assembly remain open.
The old SPY adjusted-price daily builder is not the full causal implementation.
All output receipts retain `research_ready: false`.

Host-global resource samples show available RAM above 23 GiB and unchanged
swap-out between samples, but swap-in increased. They cannot attribute activity
or prove no-swap/full-resource/V6-coexistence gates. Exact observations are in
`resource-observations.json`. V6 runtime and settings were left unchanged.
