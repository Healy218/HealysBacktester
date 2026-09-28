# V6 continual catch-up recovery — September 28, 2026

The user authorized resuming the full V6 update alongside gate 7-3. This is
research artifact creation, independent of actual paper trades; acceptance does
not deploy new weights. The 449-symbol catch-up and 40-member freeze remain open.

## Repair and preservation

The failed r1 run combined revised stock history with old feature seals, and
systemd-oomd killed its two workers at 16:49 under the old 7/8-GiB limits.
The old runner scoped its numerical memo over an entire symbol. Every new entry
prefix retained another serialized numerical result set until the symbol ended.

The selected r2 runner uses `incubator/continual/data_v2.py`: numerical reuse lasts
only one entry prefix, and spawned workers are recycled after each symbol.
Original implementation files, r1 features/labels and the anchored base dataset
remain intact. r2 rebuilds extension features and labels against the repaired
stock vintage, reusing only the retained provider evidence in `r1/market/`.
All stock/context files in the existing September 28 snapshot were independently
hash-verified (449 symbols), and its manifest SHA is pinned in the new config.

Selected config: `deploy/incubator-continual-v6-r2.json`.
Selected root: `incubator/continual-v6/r2/`.
Selected contract: `c7afdae153a72d176f2620b2800ddcf87d968eb1bd3fd2806171f3930715c6d2`.
The source contract includes the numerical memo module and new runner/launcher.

## Execution and validation

`healys-v6-continual.service` started at 18:17:38 Central for the full universe,
through September 28. Two autosized workers, CPU quota 200%, MemoryHigh 11 GiB,
MemoryMax 12 GiB, no swap; 12-hour work budget bounded by next-open-minus-30min.
The timer retains its after-close and overnight retries. The operational resume
wrapper keeps an unfinished session selected across later trading dates before
advancing to new data, and writes a separate systemd exit receipt.

Twelve focused tests passed: original candidate/training/seal tests plus cache
scope/release, exception cleanup and unfinished-date/snapshot resume coverage. Unit and
shell validation passed (unrelated pre-existing executable-unit warnings only).
At approximately 18:22, service memory was 1.46 GiB, peak 1.66 GiB. Both first
symbols progressed beyond the old revised-history failures. This is an early
resource observation, not proof that the full catch-up or training fits.

No completion ETA is established. The prior data build needed roughly 50 minutes
for each of ADI/AEHR; the new early AA/AAL progress is faster and reuses old market
captures, so extrapolating it to 449 symbols would be misleading. The previous
full-size single-member training benchmark implies about 128 minutes for 40
members before contention/evaluation. A next-day guarantee is not supported.

## Remaining proof

Inspect `latest-run.json`, per-symbol progress and service state together; a
running JSON can remain stale after an external kill. `service-exit.json` reports
systemd termination separately. Complete the catch-up, train/evaluate/freeze all
members, then measure a subsequent one-session update before closing
OPS-INCUBATOR.DATA/OPS/PROOF. Never promote a partially built or rejected model.

## Catch-up and parallel V7 checkpoint

AAL completed in 424.35 seconds: 505 candidates, 347 matured, 126 pending and
32 unfilled. The process pool continued to the next symbol; no build errors were
reported at that checkpoint. This cache-assisted first symbol is not a universe ETA.
The original base dataset hash and active source contract were checked unchanged.

V7 simultaneously advanced to `20260928-r3` path/index/integrated receipts.
Three bounded windows added 40,735 bytes. The five-path resume audit preserved all
prior fills/observed marks and both completed labels. Integrated marks rose from
185 to 195; 1,466 ledger events, three decisions and cash were unchanged.
Evidence: `v7-execution-resume-check-20260928-r3` and
`v7-integrated-prefix-check-20260928-r3` under `nn_meta/validation/`.
This remains a five-path proof; full-universe paths and reference exceptions stay open.

At the 18:37 Central follow-up, three symbols had completed with no build errors;
service memory was approximately 2.6 GiB, peak 2.7 GiB, with zero cgroup memory
high/max/OOM events. Dated receipt:
`nn_meta/validation/v6-continual-recovery-20260928/observation.json`.
