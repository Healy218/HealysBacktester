# Live, FA and operations fixes — 2026-09-05

All LO-01 through LO-15 findings in the companion audit have implementation fixes and regression coverage. No cloud commands, real notifications, production changes, commits, or trained-artifact regeneration were performed.

| Findings | Result |
|---|---|
| LO-01 | The budget monitor keeps unknown jobs active, retries failed cancellation, scopes requests to an explicit project, and waits for confirmed terminal states. Documentation describes a best-effort monitor, not a hard billing cap. |
| LO-02, LO-03 | Cloud and local workers pull complete row/marks/provenance checkpoints and delegate skip decisions to the Python builder's contract/signature/coverage validation. Upload order is marks, rows, provenance; required upload failures propagate. Local launch failures cannot end with `LOCAL-BUILD-DONE`. |
| LO-04 | Ranking filters first-capture timestamps before aggregation, removes old cross-partition duplicate evidence, and timestamps daily aggregates at their last included observation. `--prior-month` ends immediately before the new month; explicit timestamps retain exact cutoff semantics. |
| LO-05 | Both scanner CLIs use temporary state snapshots for dry runs, including pending outbox and daily digest state. Production notifications cannot be acknowledged by a console preview. |
| LO-06 | Legacy experts enqueue before deduplication and replay pending notifications after restart; their printed delivery count reflects transport success. |
| LO-07 | Scanner passes reject feeds whose last bar is more than 30 minutes old. The 16:00 ET invocation is eligible to process the final closed bar. |
| LO-08 | Whole scanner/digest transactions share an advisory lock. Individual state mutations reload under per-file locks, preserving unrelated writes and key deduplication even through stale object instances. |
| LO-09, LO-10 | FA appends serialize per source, atomically replace monthly parquets, and deduplicate identity across capture months. Empty inputs remain disk no-ops. |
| LO-11 | Tracker inputs and price indices normalize to naive UTC, including the CLI's timezone-aware timestamp. |
| LO-12 | Every comma-separated news ticker becomes an individual resolvable tag. |
| LO-13 | Graduation joins returns on ticker and ranking date, so probation and return evidence refer to the same cohort. |
| LO-14 | Daily trending applies its universe filter to cashtags as well as bare tickers. |
| LO-15 | The v6 launcher checks every worker, exits nonzero on any failure, and defaults to autosized concurrency. |

Measurement clarifications also landed: watchlist statistics use the outcome-resolution date for their trailing seven-day window; monthly ranking uses an explicit trailing 31-day score/corroboration window while the velocity baseline stays 90 days; StockTwits sentiment is labeled snapshot-weighted rather than implying unique messages. FA, GCP and systemd READMEs now distinguish committed templates from installed state and historical hardware limitations from the current machine.

CORE-13 integration: live v4/v5 candidates use `spot * (1 + MONEYNESS)` as the decision target, and the legacy scorer uses `log1p(MONEYNESS)` instead of the executed strike. The dataset reviewer owns the corresponding training convention and provenance. Legacy scoring now rejects missing/stale ensemble feature-contract tags; future legacy ensemble writers must provide the current tag (coordinated with the root reviewer). Old frozen specs/bundles must be rebuilt, evaluated and promoted under the corrected contract. They were not silently migrated or modified. The original August FA ranking likewise remains historical evidence, not a corrected benchmark.

Validation: **127 scoped tests passed**, including new failure-injection tests for describe/cancel failures, cloud/local marks upload failure, an earlier failed freeze child, legacy notification restart, dry-run pending-outbox isolation, concurrent state mutations, atomic archive failure, historical cutoff handling, cross-month duplicate identity, timezone normalization, wrong-cohort graduation, liquidity filtering, and nonzero decision-target moneyness. Modified shell scripts pass `bash -n`; `git diff --check` passes. Existing dependency deprecation/future warnings remain. The coordinating reviewer owns the final full-suite integration run.

The budget monitor remains dependent on its host and cloud API. Locks provide POSIX process coordination, not a distributed transaction across machines. Cloud checkpoint validation relies on the builder's current provenance and mark-coverage checks; a partial upload is retried/repaired instead of being counted complete by remote existence alone.

Final migration checks: new FA freezes carry `recipe_version=capture-cutoff-trailing31-v1`;
the tracker reports and excludes unversioned/stale artifacts from its prospective
scoreboard and graduation inputs. The unchanged August artifact does not count
as one of the three valid monthly rankings. Cloud freeze retries now download
and validate feature-contract version and current pool configuration hash before
skipping; stale specs rebuild. An additional targeted run passed **13 tests**,
including historical-ranking exclusion through graduation and real shell
resume flow for missing version, stale settings and current spec cases.
