# V7 dated references and retained execution frontier — September 28, 2026

Gate **7-3 remains open**. The completed entry campaign is preserved. A separate
resumable reference campaign now consumes the frozen 2,223,844-contract/date
plan across 591 securities. This is acquisition progress, not full execution
coverage or training readiness.

## Reference acquisition and evidence

- Producer: `scripts/run_v7_reference_campaign.py`, launched by
  `scripts/start_v7_reference_campaign.sh`; commit `46b1fdd`.
- Service: `healys-v7-references-20260928.service`; 16 autosized I/O threads,
  CPU quota 100%, MemoryHigh/Max 1/2 GiB, no swap, low priority.
- State: `nn_meta/validation/v7-reference-campaign-20260928/`; raw immutable
  SQLite batches: `nn_meta/data_v7/dated-reference-campaign-20260928/`.
- Campaign identity:
  `d42ad1b79591653b653339f32e971b235e941a4f09ce0d3b3cea3fb5ed2bdd76`.
- Exact existing references are reused with their original receipt anchors.
  Raw response bodies, scope, hashes and capture timestamps remain inspectable.
  Completed packs are verified on resume; source changes fail closed.
- Shared quota reservations and the authorized 10-GB free-space floor apply.
  These reference packs are local; entry overflow files on MRHA remain untouched.

The initial four-batch pilot captured 1,024 standard responses in 5.046 seconds,
retaining 975,176 bytes; readback passed. Nine packed-reference tests and seven
existing blackout tests passed. The full run resumed those four packs.

The sealed partial reconciliation at
`nn_meta/validation/v7-reference-reconciliation-20260928-partial-r0/` verifies
399,118 distinct planned pairs: 397,225 standard, 1,883 unavailable HTTP 404 and
10 rejected by the strict standard-contract validator. It retains 380,436,169
bytes across 1,613 packs. This is a bounded snapshot of a continuing campaign,
not its final count. Three auditor tests verify missing demand, duplicate
coverage and the distinction between a captured failure and an admitted input.

The ten rejected 200 responses in that snapshot have underlying/root mismatches
on FISV/FI and GAP/GPS dated contracts. They need dated identity adjudication;
they are not automatically adjusted instruments or approved exclusions.
Seven representative missing-reference pairs were also queried through both
exact expired/nonexpired list routes: all fourteen retained responses had no
matching result. Evidence is under
`nn_meta/data_v7/reference-failure-probes-20260928/`. No new blackouts were added.
The existing five exact exclusions stay unchanged. Final failure census and
adjudication are required before reference admission can close.

## Actual frontier continuation

`scripts/extend_v7_frontier_index.py` matched pending-path contracts against the
completed entry campaign and reused five packs. This moved the VKTX path forward
48 minutes without another download. A subsequent bounded lookahead captured
three actual held-contract windows (44,829 retained bytes), advancing NVDA,
VKTX and FUTU by ten further marks each. DIS/ABBV remain complete.

Selected validation roots now are:

- Paths: `v7-execution-discovery-20260928-r1/`.
- Quotes: `v7-frontier-quote-index-20260928-r1/`.
- Integrated ledger: `v7-integrated-execution-20260928-r1/`.
- Prefix comparison: `v7-integrated-prefix-check-20260928/`.

The integrated ledger preserves all 1,466 prior events, three decisions and
165 marks, adding ten marks. Cash and the existing open position are unchanged.
It stops at NVDA's next missing quote window
`[1711038750000000000,1711038780000000001)`. These are still the five retained
source cases, not a full-universe path census. Full-scope discovery, applicable
roll/reference/stock gaps and final reconciliation remain required for 7-3/7-4.
