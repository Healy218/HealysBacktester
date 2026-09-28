# V6 paper readiness repair — September 28, 2026

**V6 is operational for prospective Alpaca paper trading.** The 10:30 Central
scheduled scan completed in 243.058 seconds, within its five-minute entry window.
It scored 281 candidates with zero detection errors, using the unchanged frozen
40-member model. [Evidence](2026-09-28-v6-paper-readiness.json).

## Defects found and repaired

1. The first market-hours scan failed because VOO's adjusted prior-session prices
   had been restated after the selected snapshot was built. A new immutable
   `2026-09-25-vintage-20260928` snapshot was built; the original manifest still
   hashes to its prior external anchor. The full rebuild refreshed 66 adjusted
   histories relative to the original training-data seed, reused 23 verified
   option-context captures and regenerated dependent daily features. All 449
   symbol inputs verified. Both raw and adjusted overlap checks matched current
   captured provider prices for all 444 available symbols. The completed manifest
   SHA is `fe2ab69e315faaa710fc95f108480354d919141841b88bbc46d6b2423b78a151`.
2. The old launcher inherited `OMP_NUM_THREADS=1`, making `nproc` limit process
   sizing to one worker. Versioned launchers separate process sizing from numerical
   thread limits. The measured four-worker pass was too slow and was stopped
   before allocation. Selected v3 autosizes up to eight workers within a 12 GiB
   service cap; each numerical worker retains one thread. The complete timed scan
   peaked at 7,548,436,480 bytes (about 7.0 GiB), without an OOM or memory-limit hit.
3. A delayed research start after the session opened bypassed the runner's
   next-open cutoff calculation. Research was stopped with checkpoints preserved.
   A separate calendar-aware service condition now blocks starts from 30 minutes
   before today's open until 15 minutes after today's close. A real intraday
   service start was skipped. The source-bound research runner was not relabeled.

The repaired data was published at 10:22 Central. Scanner launcher revisions
preserve previous paper manifests under the active state's `runtime-revisions/`.
Original activation time, account fingerprint, frozen model/runtime and broker
journals remain intact. The broker continued its risk/reconciliation polling.

## Actual market-hours evidence

- Full frozen universe accounted for: 444 symbols had current bars; SATS, SAVA,
  SWTX, WBA and X had no current bars and remained explicitly listed in coverage.
- 55 signals across 48 symbols produced 281 candidate rows. The scanner selected
  five and recorded two simulated midpoint entries; these are not broker fills.
- Alpaca accepted one prospective PDD option limit order for 31 contracts. It
  remained unfilled, was automatically canceled, and reconciled to zero holdings.
  The second source entry (UVXY) was blocked after its five-minute broker window;
  the system did not backdate or force it into the account.
- At the 10:36 account check, the account was ACTIVE and eligible, with no positions
  or open orders. Later broker reconciliation showed $100,000 options buying power.
- Scanner, broker, monitor and data timers were enabled. The scanner service had
  a successful exit; broker polling remained successful. Research was inactive.

Twenty-one focused tests passed across sizing, intraday/short-session gating,
existing broker lifecycle and preflight coverage; systemd and shell validation
passed. This proves one timely full scan and actual submit/cancel/reconciliation.
A first actual fill, sustained sessions and model performance remain separate.

## Recovery and next work

Use the new selected data index; do not overwrite/relabel the old snapshot or
reset the paper account. A same-date daily refresh can reuse an already sealed
snapshot, so a provider-restatement error requires a new versioned snapshot and
validated pointer publication. Preserve the scanner's price-vintage check.

The incubator's older r1 feature history must not silently absorb these restated
inputs. Its continuation needs an explicit compatible/new lineage review;
this research task does not block the unchanged paper model. Continue the
remaining **7-3 references, actual held-path gaps and reconciliation** next.
Entry downloads are already complete and should not be repeated.

[Current state](../CURRENT_STATE.md) · [Tasks](../../TODO.md)
