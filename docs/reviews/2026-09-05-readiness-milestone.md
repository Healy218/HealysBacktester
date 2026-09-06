# Research and operational readiness — September 5, 2026

The first implementation batch starts all six authorized workstreams. Corrected
research remains blocked on source/data admission and incomplete underlying
history. Existing derived artifacts and production notifications are preserved.

Validation: **790 tests and 18 subtests passed**, ten existing/dependency warnings,
in 23.30 seconds. Source catalog, launcher preview, shell syntax and diff checks
also pass. Independent reviews found and closed acquisition-identity and
submicrosecond-timestamp gaps; contract deliverables remain explicitly unverified.

## Raw history and the newly found downloader defect

The v5/v6 cache has 500 option flat-file dates but 495 underlying dates within
2024-08-26 through 2026-08-24. Missing underlying dates are:

`2025-03-31`, `2025-07-31`, `2026-03-31`, `2026-07-31`, `2026-08-24`.

The old `cache_preflight` passes because it only requires options files for
dates already present in the underlying archive. The new local campaign runner
compares the date sets in both directions and refuses this cache. Neither check
proves sessions missing from both archives or complete per-symbol coverage.

`nn_meta.download_data._load_chunked` requested each chunk through midnight on
its last date, then advanced to the following date. That omitted every chunk's
last session. It now sends adjacent boundaries with an exclusive midnight after
the inclusive overall end date, clips each response to its own interval, and
deduplicates. Regression cases reproduce all five missing dates, including
providers that return the endpoint bar. This fixes future downloads; it does
not repair existing cache bytes automatically.

A **38 MiB, ten-file SPY pilot** was restored from the existing GCS backup using
no-overwrite copies into the previously absent `v3/data/underlying/SPY`.
[File hashes and raw coverage](2026-09-05-spy-restore.json) preserve evidence.
The restored 2025 minute bars resample to **6,448 matching OHLCV bars out of
6,448 overlapping existing SPY bars**, with zero differences in all five fields.
This supports using that backup for SPY recovery, not an untested all-symbol merge.

Four missing dates exist in the restored SPY history. The 2026 partition ends
August 18, so August 24 still requires retrieval. Earlier year partitions also
retain the known year-end omissions; 2024/2025 December 31 exist in this pilot.
The existing v5 derived cache has not been patched or replaced.

Local cache occupies about 6.8 GB; around 674 GB of disk was free at inspection.
The wider raw `v3/data`, `fa/archive`, v3 cache and SPX0 cache were absent before
the SPY pilot. GCS still exposes broader underlying and universe-daily backups.
Recovery of the full universe, compaction losses, renames and PIT coverage is
still required before a deep-history campaign.

## Isolated campaign execution

`NN_META_CAMPAIGN` places output under
`nn_meta/campaigns/<name>/<pool>/{artifacts,runs,reports,model_final}`. Historical
paths remain the default when the variable is unset. v5/v6 finalizers and loaders
now use their own bundle directories; the former v4 fallback was inappropriate
for these pools. Raw caches remain shared read inputs.

Preview a pilot with:

```sh
scripts/run_research_local.sh --campaign causal-tv-pilot --pool v6 --stage freeze --symbols SPY,QQQ
```

Stages are explicit and ordered: freeze, build, assemble, evaluate, finalize.
`--run` requires the pinned coverage preflight and a stable campaign identity.
Freeze uses per-symbol shard paths and merges the exact expected list. Outputs
are isolated, worker errors propagate, and symlink/path redirects are refused.
Immutable campaign identity binds raw-cache file lists and SHA256 bytes,
PIT/universe inputs, research code, pinned sources, launcher and runtime versions.
Changed inputs require a new campaign; checks repeat between stages and before
freeze merge. Credentials and temporary files are excluded from fingerprinting.
The launcher does not pull old cloud specs or launch cloud jobs. Existing v5/v6
families are still the configured pools; the TradingView prototypes are not
silently added by choosing a campaign name.

Old freezes, 211/441 paused v6 results, rows, marks and model bundles remain
historical. No new freeze, build, training, evaluation or finalization ran here.
No corrected performance claim follows from launcher tests.

## Observed production and home-box state

Read-only server inspection found deployed commit
`9351d01ee487299ae208393cfad021da0330950b`, preceding the merged audit repairs.
Four expert crons use the documented :01/:02/:03 staggering and worker limits.
Git-tracked code was not changed; existing untracked server files were retained.

At 2026-09-06 01:33 UTC, stock process 339599 and option process 336389 existed.
The stock heartbeat was 2026-09-05 23:37 UTC, with 443 watched symbols, zero bars
and `connecting` state; the option heartbeat was 01:33 UTC with zero quotes and
contracts. This was outside a market session. These observations establish
process/state inventory, not market-session health or signal parity.

Both **system and user** service managers report backup and StockTwits timers
`not-found`. The user deadman timer is active. Committed unit templates are not
installed jobs. No timers were installed or triggered during this milestone.
Server FA archive and v3 cache exist; server raw v3 history and SPX0 cache do not.

A full current-session stream/forced-REST comparison, restart/backfill checks,
model compatibility and coordinated code/bundle rollout remain pending. Tuesday,
September 8 is the next session named in the existing runbook; this milestone
does not claim its future observations. Do not deploy corrected source alone
against bundles rejected by the current contract.

## Contract preview and later execution

`nn_meta.live.contract_preview` consumes a captured complete Massive chain
snapshot with a receipt timestamp. It selects by expiry distance, signed delta,
spread, interest and deterministic tie-breaks after validating OCC details,
reported share count, positive bid/ask/size, timestamp availability and age.
Duplicate contracts or incomplete pagination refuse selection. Nanosecond quote
timestamps are compared without float rounding; source snapshots are hashed.
Decision/receipt ISO timestamps beyond microsecond precision are refused instead
of silently truncated. Snapshot share counts cannot establish standard
deliverables: the preview explicitly leaves deliverables unverified pending
[contract-reference data](https://massive.com/docs/rest/options/contracts/contract-overview).

The CLI emits a concrete `PREVIEW ... bid / ask / spread / delta` line and JSON.
It is a pure captured-data prototype. Quote fetching, OPRA registration, offline
selection parity, sampled spread models, quote-verified fill/roll accounting and
paper execution remain pending. No orders or notifications were sent. The
previous shared alert-format decision still precedes production wiring.

Prospective FA/PIT automation, full deep-history recovery, volatility work,
SPX0 reevaluation, stacking and RL remain ordered in TODO/ROADMAP. The August
FA cohort remains contaminated historical evidence, with zero clean prospective
monthlies toward the three-cohort gate.
