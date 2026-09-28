# Overnight entry download and V6 handoff — September 28, 2026

**V7 entry acquisition completed at 04:58:11 Central.** The selected controller
reported `entry_capture_complete`, full entry coverage, no stop reason and zero
pending tasks. Systemd reported a successful exit. The launch declaration verified.
[Observation and count reconciliation](2026-09-28-overnight-entry-completion.json).

The campaign completed/reused 10,940,386 queued ranges. The ETA denominator was
10,941,828 joined ranges before subtracting earlier indexed captures. Indexed
read-only checks of the 720 already-captured contracts across the frozen demand
found 1,443 affected joined ranges and a net reduction of 1,442 queue entries.
Thus 10,941,828 − 1,442 = 10,940,386: the final count reconciles exactly.
This was not a repeated full payload audit or a new capture campaign.

The final controller recorded 144.35 GB of retained campaign files, 144.15 GB
local free space and 743.72 GB free on MRHA. These are completion-time observations.
The final dense batch used successful time splits after page-budget exhaustion;
those retained incomplete parent attempts are not final missing coverage.

**The scheduled handoff worked:** V6 was skipped at 04:45 while V7 ran, then
started automatically at 05:00:27 Central. At the 06:17 observation its service
was still running, with four of 449 symbols completed, 3,364 candidates and
2,042 matured / 707 pending / 615 unfilled outcomes in completed-symbol receipts.
Partial work on other symbols is separately checkpointed. No training had begun,
and neither a candidate nor an accepted-model pointer existed. Memory was about
7.46 GiB, within the configured 8 GiB cap. The 06:00 daily input job succeeded.

The initial catch-up is not ready for this trading morning. The isolated
single-member benchmark did not establish full-universe build latency. Retain
the existing morning cutoff and checkpoints; do not claim a new model or a
measured nightly SLA. Only 7-3.entry closes here: references, actual held paths,
remaining gaps and reconciliation still keep the overall 7-3 gate open.

[Selected tasks](../../TODO.md) · [Current pointers](../CURRENT_STATE.md)
