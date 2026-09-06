# Expanded v6 integration milestone

The expanded v6 code is implemented behind real input gates. **The full
freeze has not started:** actual TradingView comparisons/context and complete
historical option tick coverage are still missing. A preview template or
synthetic test is not admission evidence.

| Area | Completed | Remaining before full freeze |
|---|---|---|
| TradingView features | All 13 scopes, 96 fixed causal columns | Actual chart comparisons and exact per-symbol context |
| Proposals | 8 source-default families plus existing 12; typed Setup identities | Verify actual accepted entry/exit events |
| Quote/trade features | 10 nullable columns, shared predecision contract selection, exact verified joins | Full planned-window capture and coverage |
| Download planning | Full local pre-outcome request planner; exact TRAIN/caps/weekly grids; source/input hashes | Run it on verified context, then capture the inventory |
| Freeze/build integration | New versioned contract, manifest bindings, row/candidate projection, strict launcher | Seal actual inputs and run the new campaign |
| Capture verification | Instrumented source receipts, terminal snapshots, 127 required fields/44 proposal events | Review/compile harnesses and obtain real outputs |
| Prior core pilot | Both freeze shards and merged spec; IBKR rows/marks; SPY MA partial | Preserved as prior-contract evidence; superseded |

The new selected-contract sample contains **17,814 quotes and 648 reported
trades** across SPY call/put contracts expiring August 25, selected from the
August 24 raw close 762.19. Both exact 15-minute windows materialize and join;
all ten numeric features are present. Code-209 eligibility admits 45 call
trades and 314 put trades, preserving excluded/raw audit counts. This is a
bounded integration test, not full data coverage or evidence of predictive gain.
[Capture/store evidence](2026-09-06-v6-selected-tick-store.json).

The stopped core pilot's final full fingerprint matched **123,711 inputs**,
with no additions/removals/byte changes. It completed 12-family freezes for
SPY and IBKR, IBKR's 8,910 rows/95,159 marks, and SPY's 984-row MA partial.
It did not assemble or produce an evaluated model. The descriptor is retired
and its real nonzero stop status remains visible.
[Preservation evidence](2026-09-06-core-pilot-stop.json).

Final main-checkout regression: **1,390 tests and 18 subtests passed**,
11 warnings in 45.43 seconds. Shell syntax and diff checks pass. The
implementation was independently reviewed across feature, proposal, admission
and tick-store boundaries. No evaluated-model or CI result is inferred.
[Input schema and ordered completion](../specs/V6_EXPANDED_INPUTS.md).

Prior work also completed the 51 audit repairs plus four additional concerns,
corrected raw/all-adjusted stock history and raw option context, sealed the
candidate, repaired provider-cache isolation, and added socket recording and
closed-bar/reconnect safeguards. [Earlier complete overview](2026-09-06-rebuild-milestone.md).

Near-live deployment remains a later gate: richer receipt/condition mapping,
full-session historical/live parity, performance, evaluated new bundle and
coordinated server rollout. No model training, server deployment, notification
or trading action occurred in this integration.
