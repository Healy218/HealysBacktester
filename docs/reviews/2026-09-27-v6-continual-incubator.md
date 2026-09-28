# V6 continual research incubator — September 27, 2026

The incubator now extends research data and trains new model candidates independently
of paper trades. V6 is the selected generation. The original frozen dataset and
40-member model remain unchanged. [Evidence](2026-09-27-v6-continual-incubator.json).

## Implemented and activated

- Full frozen-universe candidate enumeration with immutable per-entry features,
  completed simulated option labels, pending/unfilled inventories and hash-checked
  resume. An incomplete option path cannot become a completed training outcome.
- Historical base plus non-overlapping extensions; streamed training arrays;
  chronological validation with outcome-end purging and one-day embargo.
- Fixed-family member retraining, incumbent and constant-baseline diagnostics,
  immutable candidate freezes, and separate latest-candidate/latest-accepted pointers.
  Rejection or failure preserves the previous accepted model. No automatic promotion.
- `healys-v6-continual.timer` installed and enabled; old
  `healys-ai-incubator-after-close.timer` disabled. New service started at
  19:59:57 Central September 27 for the August 25–September 25 catch-up, 449 symbols.
- Scheduled at 16:45 New York weekdays, with 05:15 and 07:15 New York Monday–Saturday
  retries. Eight-hour work budget, next-open-minus-30-minute cutoff, two autosized
  workers at most, 8 GiB memory limit and two-CPU quota. The service skips starts
  while the existing daily input producer is active.

## Measured evidence

39 focused tests passed, including real LightGBM fit/resume, temporal purge,
immutable seals, candidate enumeration and rejected-pointer retention. Final
systemd unit verification passed. The original V6 release independently verified
against its external SHA-256 after the benchmark.

The corrected SPY August 25–28 pilot produced 160 candidates: 98 matured,
54 pending and 8 unfilled, in 127.26 seconds using previously captured market data.
An earlier exploratory pilot admitted six incomplete execution paths; those labels
are excluded from the corrected lineage and training benchmark. The final source
and frozen-configuration smoke run built 16 pending SPY candidates in 22.03 seconds.

The full-size training benchmark combined the original 4,281,562-row base with the
98-row SPY extension. Purging yielded 2,769,473 training and 223,091 validation rows.
Array preparation took 12.19 seconds; one classifier/magnitude member took 191.32
seconds. Total 205.81 seconds, peak RSS 6,833,776 KiB, cgroup peak 7.1 GiB.
Forty times the member timing is about 128 minutes; this excludes full-universe
capture, evaluation and contention, and is not an overnight completion promise.

## Evidence limits and next measurement

The full-universe catch-up was started, not completed, at this checkpoint. A full
40-member freeze and a subsequent one-session update must finish before closing
OPS-INCUBATOR.PROOF. Pilot timing cannot predict 449-symbol catch-up latency.
Newly arriving data enters research artifacts daily; the latest 40 observed dates
are validation data and do not enter weight fitting until outside that tail.
The initial validation tail overlaps the original incumbent's training period;
its comparison is diagnostic, not an independent performance test. Research labels
retain V6's historical aggregate execution assumptions, not actual broker fills.

The active contract binds local V6 source hashes, including pre-existing research
checkout work; commit c478dbb alone is not a portable copy of all existing V6 runtime
inputs. Reuse the selected installed checkout and frozen release. A changed runtime
requires a new research lineage, never relabeling an existing completed artifact.

[Contract](../specs/AI_INCUBATOR.md) · [Current pointers](../CURRENT_STATE.md) ·
[Selected tasks](../../TODO.md)
