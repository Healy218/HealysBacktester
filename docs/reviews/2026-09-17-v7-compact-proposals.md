# V7 compact proposals and stored feature joins

Proposal batches previously repeated the strategy parameters, policy and string
timestamps in every JSON record. The new `v7-compact-proposals-v2` format stores
typed Parquet rows with the complete variant dictionary and simulator policy in
the immutable declaration. It reconstructs public proposal IDs and fields exactly.
Writes and reads use bounded batches; all registered variants remain in the
catalog, including variants with no admitted entries. Streaming the simulator's
trade records also avoids materializing an entire repeated-metadata batch.

The captured-input builder now binds the active coverage inventory and applies
dated membership at the entry decision. A later exit is retained even if the
security has left the universe; dated entry and exit ticker routing is preserved.
Membership availability after a decision cannot admit that decision. Empty
membership preserves the variant census with zero admitted proposals. Unresolved
source identities and actions still stop this builder.

`StoredFeatureRows` connects saved observations to the existing 222-column row
contract, dated sectors, prior-session daily context, and selected-contract tick
features. Saved moving averages include their exact contemporaneous price units,
so the first observation after a split retains its preceding warmup and reproduces
the direct arithmetic. It must not recompute these averages from a truncated
saved epoch. Raw stock prices remain separate for option selection and moneyness.
The adapter caches one epoch; an assembly consumer should process by epoch for
efficient reuse and verify all bindings at completion.

This adapter does not manufacture daily or tick data. Its tests use explicit
fixtures for these components; full captured daily/market context, actual
proposal-driven quote demand, option outcomes, labels, folds and the training
runner still need integration. Current proposals use the amended strategy-only
simulator configuration; option-premium stops belong to the subsequent option
replay. Proposal completion does not establish execution or training readiness.

## Verification

Component tests compare every reconstructed proposal field against the direct
simulator, and all 222 feature values against direct causal epochs. They cover
membership availability, exits after membership ends, dated renames, zero-entry
catalogs, bounded row groups, corrupted files, rejected lossy records and restart
after an interrupted batch. The first post-split MA feature observation is an
explicit feature probe; it is not represented as a generated strategy signal.

The complete regression suite passed 1,967 tests and 18 subtests, with 18 warnings
in 154.81 seconds. No new data downloads or V6 runtime changes were made.

Real AAPL data for March 15–May 10, 2022 produced 757,595 proposals across all
11,268 variants. A separate audit reran the simulator from saved signal channels,
applied dated membership independently, and compared every reconstructed public
field in every row. All matched. This tests storage/proposal parity, not an
independent proof of the simulator itself. Membership excluded zero AAPL entries
in this window; nonmember filtering is covered by component tests.

| Timeframe | Variants | Proposals | Censored at endpoint |
|---|---:|---:|---:|
| 1 minute | 2,817 | 598,931 | 2,099 |
| 5 minutes | 2,817 | 108,336 | 1,828 |
| 15 minutes | 2,817 | 34,238 | 2,294 |
| 30 minutes | 2,817 | 16,090 | 2,228 |

The proposal Parquet files occupy **9,896,112 bytes**, versus **807,083,883 bytes**
for the exact same current-policy rows serialized using the former JSON layout:
a **98.77% reduction**. Complete feature/proposal output, including declarations
and provenance, occupies **108,089,486 bytes**. This comparison does not use the
superseded stock-stop pilot's different rows as its denominator.

The slowest build worker took 174.71 seconds and peaked at 918,820 KiB RSS. Four
outer workers used one inner thread each. Completed-run resume took 4.05–4.15
seconds per worker and preserved all **736 completion receipts** byte-for-byte.
These are bounded pilot measurements, not full-history memory, storage or
V6-coexistence admission.

Evidence: `nn_meta/validation/v7-compact-proposal-verification-20260917`, receipt
`2ddac7740426c8fb411f97ab5bf5cb39096a5eee4fc11fbd752f68ea605a30ad`.
It retains build/resume/exact-comparison logs, exact audit source, tests/XML,
source/receipt bindings and measured counts. Build artifacts are under
`nn_meta/validation/v7-compact-proposal-build-20260917`.

The fresh readiness report `v7-readiness-20260917-compact.json` still fails all
eight substantive stage gates. This milestone does not mark any full-universe
stage complete or launch training.
