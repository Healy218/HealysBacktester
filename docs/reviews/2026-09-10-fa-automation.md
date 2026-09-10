# Prospective FA automation and job health

Implemented in isolated branch `ops/fa-automation-20260910`, based on corrected
main. Neither main's pinned campaign source nor the legacy production branch
was changed. The user authorized continuing this coding independently of the
next-sale accounting check. Nothing was installed, enabled, collected, uploaded
or restored against a live provider during implementation.

## Monthly cohorts

`python -m fa.monthly` previews the previous calendar month's exact UTC cutoff.
`--run` freezes only during the first seven UTC days of the new month. Thus the
September 10 preview refuses to create a late August cohort; the next normal
freeze is October 1 for September captures. Missing that window leaves a gap,
not a retroactive prospective claim. This seven-day operational window is a
new explicit automation policy; actual publication time still determines when
forward measurement can begin.

A new cohort lives in `fa/artifacts/prospective/YYYY-MM/`. It contains:

- A copy of each source's archive partitions, acquired under its writer lock.
- Captured liquidity/training baseline lists and aliases when available.
- The corrected capture-cutoff recipe's ranking JSON and Markdown.
- A manifest with input/output hashes, recipe/source hashes, cutoff, publication
  time, tracking start and ranking count.

A single monthly lock serializes freezes and tracking writes. A completed
cohort is verified and reused on rerun without recomputing from changed inputs.
Failed snapshots retain `.pending-*` evidence and do not publish a completed
cohort. Corrupt sealed inputs refuse reuse. Empty archives are refused; a valid
archive with no corroborated picks can produce a zero-pick cohort, which is not
proof of useful prospective performance. Snapshotting is an additional local
copy of FA archives; size/storage should be checked before installation.

Publication is separate from the historical input cutoff. Daily forward
measurement starts after the publication UTC date, preventing an already-known
month-end return from becoming forward evidence. Existing August historical
rankings are neither rewritten nor counted. The new cohort directory stays
separate from the legacy tracker/graduation path; no PIT membership changes or
automatic graduation are applied.

## Forward reports

```sh
python -m fa.monthly --root /path/to/cohorts --track-only --prices /path/to/daily-prices --run
```

Supply one `TICKER.parquet` per pick and frozen baseline member, containing a
datetime index and `Close`. No downloads occur. All names must have at least
two positive finite prices and exactly matching observed dates. Missing names,
duplicate dates, or mismatched coverage fail instead of silently shrinking the
baseline. The report includes requested cutoff, actual observed start/end,
input price hashes and each pick's excess return. Observed end can precede the
requested date: these checks do not certify exchange-calendar completeness.
Reports are dated, write-once and hash-checked on retry. Today is excluded from
the CLI's daily measurement cutoff. Prices must be consistently adjusted by
their upstream producer; this module does not validate split adjustment quality.

`healys-fa-monthly` schedules October-style month-start freezes at 00:15 UTC;
`healys-fa-tracker` schedules tracking at 01:00 UTC daily. The tracker requires
`FA_DAILY_PRICES` in the optional host `deploy/fa-automation.env` file or an
explicit CLI `--prices` path. A missing configured price path fails visibly.
Templates target the eventual home deployment path; they are not installed.

## Receipts and health

`fa.collect` now records per-source running/success/failure/skipped receipts.
The existing aggregate exit policy remains: any successful collector yields
exit 0, but a failed individual source remains independently visible.
Zero new rows means the collector completed, not that capture freshness passed.

`run_ops_job.py` wraps scheduled commands with a non-overlap lock, timeout,
per-run log, latest attempt and separate last-success receipt. Timeout terminates
the command process group. A missing command, timeout or failed attempt cannot
be hidden by the previous success. The backup and StockTwits systemd templates
now use this wrapper; underlying transfer commands are unchanged.

```sh
python scripts/check_ops_health.py \
  --job fa-monthly:768 --job fa-tracker:48 \
  --job cache-backup:192 --job stocktwits-push:3 \
  --source stocktwits:3
```

Thresholds are explicit hours. JSON output and exit 1 report missing, failed,
running, stale, future-dated or malformed evidence. Capture freshness uses
`ts_utc` in the latest partition, never the file modification time. On the
server, check configured sources independently, e.g. `--job collector-news:3`;
do not require a source deliberately disabled on that host. This CLI does not
send notifications. The provided `healys-data-health` hourly timer/service
records JSON in the journal and fails visibly on gaps. Its initial thresholds
are 32 days for the monthly run, 48 hours for the tracker, eight days for
backup, and three hours for StockTwits job/captures. Install it only alongside
the jobs it monitors; it will correctly fail before initial successful runs.

## Bounded backup restore

```sh
python scripts/verify_backup_sample.py \
  --source /path/to/original.parquet \
  --object gs://bucket/exact/object.parquet
```

Default is preview. `--run` downloads exactly that object into temporary storage,
compares SHA-256 against the source before and after download, and writes a
`backup-restore` receipt. It never restores over the original or deletes remote
objects. Verification covers one explicit object, not entire backup completeness.
Tests use a local fake copy transport; no real GCS restore has been performed.

## Activation prerequisites

Before installing schedules, deploy this corrected FA code in a compatible
checkout without modifying the active v6 campaign, establish the intended
archive/data sync ownership, check archive freshness and disk headroom, and
configure daily price files. The production branch still carries older FA
semantics; do not transplant just the scheduler into that branch. Inventory the
installed system/user timers separately; repository templates do not prove
installation or a successful live run. No existing collectors or backups were
stopped by this work.

## Validation

Full suite: 1,469 tests plus 18 subtests passed. Final focused run: 17 passed
after the publication-label change and descendant-timeout regression test.
The first full run's two launcher errors were isolated-checkout setup failures
(missing venv path); linking the existing environment resolved both. No new
dependencies were installed. systemd-analyze verify passed for all changed/new
units, and git diff --check passed. Main's tracked working tree stayed unchanged
through implementation; only its pre-existing untracked artifacts were present.
