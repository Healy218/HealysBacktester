# V6 paper quote recovery — October 1, 2026

## Defect and evidence

User selected reliable V6 Alpaca paper operation. At 14:15, 14:30 and 14:45
Central, a missing fresh FLY quote aborted the whole scanner before candidate
computation. Broker polling independently retried every 15 seconds. The prior
TLT input-vintage repair remained valid; this was a separate monitoring problem.

A read-only comparison at 14:58:03 found identical Massive and Alpaca OPRA quotes
for FLY261120P00023000: bid 2.70, ask 3.30, quote time 14:57:59.050690141.
The preceding quote was 14:57:07.843373808, a 51.207-second interval. This sample
supports a quiet-tape explanation; it does not prove every historical failure had
the same cause. Query receipt: `nn_meta/validation/v6-paper-quotes-20261001-r0/initial-probe.json`.
Retrieval time remains distinct from the exchange timestamp.

## Versioned repair

Scanner launcher v10 uses the same memory-aware allowance: up to 11 processes,
16 GiB maximum / 14 GiB high, one numerical thread per process. It selects
`scripts/run_v6_forward_resilient_v1.py`, derived from the admitted frozen scanner
SHA `cfdee72d1a8ee9b386825a255412007bc108bbe73b5b2f2b001afcd9398137c2`.
All feature, model, portfolio, pricing and provider modules still import from
the verified frozen checkout. Its original files and activation hashes are intact.

Held-position monitoring now runs in a separate thread/provider session while
full-universe detection and feature capture proceed. Only the exact empty-fresh-
quote error is retried, at two-second intervals, for up to a 120-second retry
budget, capped at signal close +270 seconds. Existing provider call timeouts
remain in effect; the retry budget cannot interrupt an in-flight request.
Other errors remain blocking. Before allocation, the scanner requires successful
monitoring; unresolved risk blocks all new entries. Candidate receipts survive
a monitoring failure. The frozen five-minute entry deadline and 30-second quote
validation remain enforced. No stale quote is relabeled, synthesized or priced.
The former all-five-slots shortcut is omitted: full candidate computation may
now run while monitoring resolves, even when capacity ultimately stays zero.

The independent broker risk poll and order policy are unchanged. This repair
addresses scanner aborts, not all causes of missed windows. Full-scan timing under
market load and prospective quote recovery remain to be observed next session.

## Deployment and verification

Installed drop-in: `healys-v6-alpaca-scanner.service.d/95-monitor-v10.conf`.
Current paper manifest SHA:
`06459ec7cb58784cc35af07030c88f0685540a167074dd1c97fcb0a30e150f9c`.
Prior manifest and merged unit preserved in paper state:
`runtime-revisions/scanner-monitor-v10-20261001/`.
An initial installer attempt rejected a transcribed parent hash before any
runtime modification; the corrected comparison passed. Existing source hashes
were verified, not rewritten to excuse changed frozen artifacts.

At 15:32:54–15:32:57 Central the installed v10 service started and exited
successfully, verified all 449 symbols and unchanged model, and reported
`idle / outside_market_hours`. The scanner elapsed receipt was 1.718 seconds;
this is an idle-startup measurement, not market-hours scan performance.
At 15:34 both scanner/orders timer enablement links remained present; broker
receipt was `market_closed`. Prior manifest fields and admitted files were
independently checked unchanged. No manual paper orders were submitted.

55 focused tests passed: concurrent recovery/allocation gating, persistent and
fatal errors, quote freshness, portfolio deadlines/deduplication, source
reconciliation, resource sizing and watcher visibility. Consumer import from
the actual frozen checkout and shell/Python syntax checks passed.
Evidence: `nn_meta/validation/v6-paper-quotes-20261001-r0/{deployment,verification}.json`.

## Next-session acceptance

Inspect `position-monitor-status.json` for attempts and terminal outcome, and
`status.json` / `scanner-dispatch-status.json` for timely completed passes.
The hourly watcher includes these receipts plus independent broker status.
An after-hours idle pass does not establish restored market-hours reliability.
Do not close OPS-PAPER.RELIABILITY until prospective passes and actual broker
reconciliation support it; no trades are manufactured to satisfy the check.
