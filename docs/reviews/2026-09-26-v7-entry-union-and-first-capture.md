# Full entry union and first actual option capture — September 26, 2026

The demand recovery and queued union audit completed while the preparation
checkpoint was being saved. The earlier 550/591 snapshot is historical.
All 591 demand checkpoints now exist and the recovery completed without errors.
The original 546 checkpoints, frozen catalog, producer sources and runtime
receipts were preserved. The exact kernel exception remains separately proven.

## Full actual entry demand

`nn_meta/validation/v7-3-entry-union-20260926` is the immutable full audit:

| Measure | Result |
|---|---:|
| Securities | 591 |
| Admitted proposals | 793,394,264 |
| Input/unique requests | 76,910,536 |
| Union captures | 42,030,534 |
| Quote captures | 21,015,267 |
| Trade captures | 21,015,267 |
| Contracts | 1,057,177 |
| Contract-days | 2,223,844 |
| Union seconds, each kind | 14,404,985,220 |
| No-contract target outcomes | 2,605,230 |
| No-fresh-spot target outcomes | 770,705 |
| Selected target outcomes | 98,350,120 |
| Distinct demand input bindings checked | 2,027,648 |

The audit verified checkpoint/declaration/export identity and hashes, checked
runtime admission and input bindings, reconciled every request count, globally
unioned bounded contract/day windows and checked each request's interval coverage.
It wrote a small census, not duplicate request tables. This covers pre-decision
entry features only. Full execution-path coverage and training readiness remain
false. Demand completed at 06:03:03 UTC; union completed at 06:27:56 UTC.

## Bounded real capture and capacity forecast

The user requested actual option captures. The first chronological SPY quote
request from the preserved demand, with its matching trade request, was selected
before provider inspection. This consumes an actual missing entry-feature input:
`SPY220316P00420000`, March 15, 2022,
[1647351270000000000, 1647351600000000000) SIP nanoseconds.

The sealed plan at `v7-first-actual-capture-plan-20260926` binds the full union,
SPY demand receipt and existing capture/provider sources. Two capture windows
plus the metadata reservation give a conservative 3 GiB capacity ceiling using
the existing capturer's per-shard oversize rejection. Free disk was 158.07 GB;
that allocation retains over 100 GiB free. The conservative project ceiling,
including the full existing demand allocation and 1 GiB extra metadata allowance,
was 575.87 GB against 640 GB. Shared acquisition quota also covers the allocation.
This is a bounded batch forecast, not a whole-universe byte forecast.

```bash
./venv/bin/python scripts/capture_v7_quotes.py \
  --requests nn_meta/validation/v7-first-actual-capture-plan-20260926/requests.json \
  --output nn_meta/data_v7/entry-first-actual-20260926 \
  --budget-root nn_meta/data_v7 --workers 2
```

Capture succeeded: **3,239 quote records and 1,208 trade records**, one complete
provider page each. Receipt hashes, raw record SHA256, counts, kind, contract and
interval bounds all passed `verify` and `verify_capture`. Total output: **73,313
bytes**. Shared quota is **68,973,094,838 / 250,000,000,000 bytes**, with no pending
reservations. The raw receipts remain under `nn_meta/data_v7/entry-first-actual-20260926`;
verification is sealed at `nn_meta/validation/v7-first-actual-capture-verified-20260926`.
This demonstrates pre-February-2024 access for this contract/window only.

## Remaining capture and training gate

Actual capture has begun, but the full 42-million-window acquisition is not
launched. Only about 50.69 GB can currently be added while maintaining the
100 GiB disk reserve. The acquisition quota alone does not establish local disk
feasibility. Reuse the existing captures and measure a full-scope volume/storage
forecast, including metadata/file layout, before bulk expansion. Do not
extrapolate a single SPY case or the old SPY-only volume pilot to the universe.

Dated standard-contract metadata/hours and row integration remain missing for
this new window. Full entry fills, marks, exits, rolls and stock-delivery demand
remain distinct V7-3 work. Integrated execution, assembled labels/features,
fold/trial/resource evidence and the full readiness gate are still required.
**Training has not started; V7-3 remains open.**

The separate terminal monitor and retired hourly alerts are recorded in
`2026-09-26-v7-capture-preparation.md`. Both obsolete home timers remain disabled.
Full tests previously passed 2,415 tests and 18 subtests; no production source
changed afterward, and actual provider artifacts were verified independently.
